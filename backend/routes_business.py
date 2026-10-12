# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re
from decimal import Decimal

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, NOT_STARTED, checklist, filing_page, filing_to_dict, record_filed, refresh_status, set_tick,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, date, iso, money, my_business, read_amount,
    read_upload, remove_document, role_required, send_document, state_code, now,
)
from models import (
    Business, ComplianceItem, Document, NicCode, PenaltyRule, RegulatoryProfile, RuleThreshold, db, now,
)

ENTITY_TYPES = ("individual", "proprietorship", "partnership", "llp", "private_limited")
COMPANY_TYPES = ("llp", "private_limited")
# The profile lines shown in "What changed" after an edit.
PROFILE_LINES = ("msme_tier", "gst_scheme", "itr_form", "presumptive_eligible", "audit_applicable",
                 "other_audit_applicable", "files_24q", "files_26q")
# Codes people type, the pattern each must match, and the message when it does not.
CODES = {
    "pan": (r"[A-Z]{5}[0-9]{4}[A-Z]", "Enter a valid PAN."),
    "gstin": (r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", "Enter a valid GSTIN."),
    "tan": (r"[A-Z]{4}[0-9]{5}[A-Z]", "Enter a valid TAN."),
    "udyam_number": (r"UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}", "Enter a valid Udyam number."),
    "cin_llpin": (r".{1,21}", "Enter your CIN or LLPIN."),
}


def read_business_form(data):
    """(values, None) for a correct registration form, or (None, error answer)."""
    values = {}
    for field, longest in (("legal_name", 200), ("address", 500), ("description", 1000)):
        text = str(data.get(field) or "").strip()
        if not text or len(text) > longest:
            message = f"Fill in {field.replace('_', ' ')} (up to {longest} characters)."
            return None, error(422, "VALIDATION_ERROR", message)
        values[field] = text
    if data.get("entity_type") not in ENTITY_TYPES:
        return None, error(422, "VALIDATION_ERROR", "Choose the type of business.")
    if state_code(data.get("state")) is None:
        return None, error(422, "VALIDATION_ERROR", "Choose your state from the list.")
    values["entity_type"], values["state"] = data["entity_type"], data["state"]
    for field in ("annual_turnover", "investment_amount"):
        values[field] = read_amount(data.get(field), 0, 9999999999)
        if values[field] is None:
            return None, error(422, "VALIDATION_ERROR", f"Enter the {field.replace('_', ' ')} in rupees.")
    for field in ("gst_registered", "deducts_tds", "pays_salary_above_limit", "gst_composition",
                  "gst_qrmp", "accounts_audited_other_law"):
        values[field] = data.get(field, False)
        if not isinstance(values[field], bool):
            return None, error(422, "VALIDATION_ERROR", f"Answer {field.replace('_', ' ')} with yes or no.")
    for field, (pattern, message) in CODES.items():
        code = str(data.get(field) or "").strip().upper() or None  # stored in capitals
        if code and not re.fullmatch(pattern, code):
            return None, error(422, "VALIDATION_ERROR", message)
        values[field] = code
    phone = data.get("phone")
    if not isinstance(phone, str) or not re.fullmatch(r"[6-9][0-9]{9}", phone):
        return None, error(422, "VALIDATION_ERROR", "Enter a 10-digit mobile number.")
    values["phone"] = phone

    # Answers that are needed only for some businesses.
    if not values["pan"]:
        return None, error(422, "VALIDATION_ERROR", "Enter a valid PAN.")
    if values["gst_registered"] and not values["gstin"]:
        return None, error(422, "VALIDATION_ERROR", "Enter your GSTIN (you said you are GST registered).")
    if values["gst_registered"]:
        gstin_problem = gstin_error(values["gstin"], values["pan"], values["state"])
        if gstin_problem:
            return None, error(422, "VALIDATION_ERROR", gstin_problem)
    if values["gst_composition"] and not values["gst_registered"]:
        return None, error(422, "VALIDATION_ERROR", "Only a GST-registered business can use composition.")
    if values["deducts_tds"] and not values["tan"]:
        return None, error(422, "VALIDATION_ERROR", "Enter your TAN (you said you deduct TDS).")
    if values["entity_type"] in COMPANY_TYPES and not values["cin_llpin"]:
        return None, error(422, "VALIDATION_ERROR", "Enter your CIN (company) or LLPIN (LLP).")

    # Forget answers that do not apply, e.g. a GSTIN sent with gst_registered = false.
    if not values["gst_registered"]:
        values["gstin"] = None
    if not values["deducts_tds"]:
        values["tan"] = None
    if not values["gst_registered"] or values["gst_composition"]:
        values["gst_qrmp"] = False
    if values["entity_type"] not in ("partnership", "llp"):
        values["accounts_audited_other_law"] = False
    if values["entity_type"] not in COMPANY_TYPES:
        values["cin_llpin"] = None
    return values, None


def limit(key):
    """A legal limit from the rule_thresholds table, e.g. limit("gst.qrmp.max_turnover")."""
    row = (RuleThreshold.query.filter(RuleThreshold.key == key, RuleThreshold.effective_from <= now())
           .order_by(RuleThreshold.effective_from.desc()).first())
    if row is None:
        raise RuntimeError(f"The rule {key} is missing. Run: python seed.py")
    return row.value


def compute_profile(business):
    """Which rules apply to the business: MSME tier, GST scheme, ITR form, audits, TDS returns."""
    turnover, entity = business.annual_turnover, business.entity_type

    # MSME tier: the smallest tier whose investment AND turnover limits both fit.
    msme_tier = "not_msme"
    for tier in ("medium", "small", "micro"):
        investment_fits = business.investment_amount <= limit(f"msme.{tier}.max_investment")
        if investment_fits and turnover <= limit(f"msme.{tier}.max_turnover"):
            msme_tier = tier

    registration_limit = limit("gst.registration.min_turnover")
    if not business.gst_registered:
        gst_scheme = "not_registered"
    elif business.gst_composition and turnover <= limit("gst.composition.max_turnover"):
        gst_scheme = "composition"
    elif business.gst_qrmp and turnover <= limit("gst.qrmp.max_turnover"):
        gst_scheme = "regular_qrmp"  # quarterly returns, the business's choice within the limit
    else:
        gst_scheme = "regular_monthly"

    # Presumptive scheme (s.44AD): not for LLPs and companies. Tax audit (s.44AB): above the
    # turnover limit, but never with the presumptive scheme. Companies always have their
    # accounts audited; firms and LLPs answer that question on the form.
    presumptive = entity not in COMPANY_TYPES and turnover <= limit("itr.presumptive_44ad.max_turnover")
    tax_audit = not presumptive and turnover > limit("itr.audit_44ab.min_turnover")
    other_audit = entity == "private_limited"
    if entity in ("partnership", "llp"):
        other_audit = business.accounts_audited_other_law

    if entity == "private_limited":
        itr_form = "itr_6"
    elif entity == "llp":
        itr_form = "itr_5"
    elif presumptive:
        itr_form = "itr_4"
    elif entity == "partnership":
        itr_form = "itr_5"
    else:
        itr_form = "itr_3"

    suggest_gst = not business.gst_registered and turnover > registration_limit
    explanations = {"gst_scheme": "", "roc_not_tracked": ""}  # the two notices the page shows
    if suggest_gst:
        explanations["gst_scheme"] = (f"Not registered, but turnover is above {format_inr(registration_limit)}: "
                                      "you may need GST registration. Ask a CA.")
    if entity in COMPANY_TYPES:
        explanations["roc_not_tracked"] = "LLPs and companies also have ROC/MCA filings, which this app does not track."
    return {"msme_tier": msme_tier, "gst_scheme": gst_scheme, "gst_registration_suggested": suggest_gst,
            "itr_form": itr_form, "presumptive_eligible": presumptive, "audit_applicable": tax_audit,
            "other_audit_applicable": other_audit,
            "files_24q": business.deducts_tds and business.pays_salary_above_limit,
            "files_26q": business.deducts_tds, "roc_not_tracked": entity in COMPANY_TYPES,
            "explanations": explanations, "rule_version": "v2", "computed_at": now()}


def business_page(business):
    """{business, profile, nic_code}: what the business page shows."""
    fields = ("legal_name", "entity_type", "state", "address", "description", "pan", "phone", "gst_registered",
              "gstin", "gst_composition", "gst_qrmp", "accounts_audited_other_law", "deducts_tds", "tan",
              "pays_salary_above_limit", "cin_llpin", "udyam_number")
    info = {"id": str(business.id), "annual_turnover": money(business.annual_turnover),
            "investment_amount": money(business.investment_amount),
            "state_needs_review": state_code(business.state) is None}  # a state typed before the list
    for field in fields:
        info[field] = getattr(business, field)
    profile = RegulatoryProfile.query.filter_by(business_id=business.id).first()
    profile_info = None
    if profile:
        profile_info = {"gst_registration_suggested": profile.gst_registration_suggested,
                        "roc_not_tracked": profile.roc_not_tracked, "explanations": profile.explanations,
                        "rule_version": profile.rule_version, "computed_at": iso(profile.computed_at)}
        for line in PROFILE_LINES:
            profile_info[line] = getattr(profile, line)
    nic = db.session.get(NicCode, business.nic_code_id) if business.nic_code_id else None
    nic_info = {"code": nic.code, "description": nic.description} if nic else None
    return {"business": info, "profile": profile_info, "nic_code": nic_info}


# --- Registering and editing the business ---


@app.route("/api/v1/onboarding/business", methods=["POST"])
@role_required("business")
def register_business():
    values, problem = read_business_form(request.get_json(silent=True) or {})
    if problem:
        return problem
    if my_business():
        return error(409, "BUSINESS_EXISTS", "You have already registered your business.")
    business = Business(user_id=current_user().id, **values)
    db.session.add(business)
    db.session.flush()
    profile = RegulatoryProfile(business_id=business.id, **compute_profile(business))
    db.session.add(profile)
    sync_filings(business.id, profile, now())  # this year's filings
    db.session.commit()
    return jsonify(business_page(business)), 201


@app.route("/api/v1/onboarding/business", methods=["GET"])
@role_required("business")
def get_business():
    business = my_business()
    if business is None:
        return error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    return jsonify(business_page(business))


@app.route("/api/v1/onboarding/business", methods=["PUT"])
@role_required("business")
def update_business():
    business = my_business()
    if business is None:
        return error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    values, problem = read_business_form(request.get_json(silent=True) or {})
    if problem:
        return problem
    for field in values:
        setattr(business, field, values[field])
    profile = RegulatoryProfile.query.filter_by(business_id=business.id).first()
    old = {line: getattr(profile, line) for line in PROFILE_LINES}
    new = compute_profile(business)
    for field in new:
        setattr(profile, field, new[field])
    filings = sync_filings(business.id, profile, now())
    db.session.commit()
    changed = []
    for line in PROFILE_LINES:
        if old[line] != new[line]:
            changed.append({"line": line, "old": old[line], "new": new[line]})
    page = business_page(business)
    page["changes"] = {"profile": changed, "filings": filings}
    return jsonify(page)


@app.route("/api/v1/onboarding/states")
@role_required("business")
def list_states():
    return jsonify([{"name": state["name"], "code": state["code"]} for state in GST_STATES])


@app.route("/api/v1/onboarding/nic-codes")
@role_required("business")
def search_nic_codes():
    """Up to 20 NIC codes whose code or description contains ?q=."""
    words = request.args.get("q", "").strip()[:100]
    if len(words) < 2:
        return jsonify([])
    pattern = f"%{words}%"
    codes = (NicCode.query.filter(NicCode.code.ilike(pattern) | NicCode.description.ilike(pattern))
             .order_by(NicCode.code).limit(20))
    return jsonify([{"code": nic.code, "description": nic.description} for nic in codes])


@app.route("/api/v1/onboarding/business/nic-code", methods=["PUT"])
@role_required("business")
def set_nic_code():
    business = my_business()
    if business is None:
        return error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    code = str((request.get_json(silent=True) or {}).get("code") or "").strip()
    nic = NicCode.query.filter_by(code=code).first()
    if nic is None:
        return error(422, "UNKNOWN_NIC_CODE", "Choose a code from the NIC list.")
    business.nic_code_id = nic.id
    db.session.commit()
    return jsonify({"code": nic.code, "description": nic.description})


@app.route("/api/v1/onboarding/autofill", methods=["POST"])
@role_required("business")
def autofill():
    """Values for the registration form, read from a GST certificate or PAN card (not stored)."""
    upload, data, problem = read_upload()
    if problem:
        return problem
    try:
        text = ocr.extract_text(data, upload.mimetype)
    except ValueError as reason:
        return error(422, "DOCUMENT_UNREADABLE", f"We could not read this file. {reason}")
    return jsonify({"found": ocr.read_registration(text)})


# --- The calendar and the filing page ---


def find_filing(item_id):
    """(business, filing) of the logged-in business, or (None, error answer)."""
    business = my_business()
    if business is None:
        return None, error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    filing = db.session.get(ComplianceItem, item_id)
    if filing is None or filing.business_id != business.id:
        return None, error(404, "FILING_NOT_FOUND", "This filing was not found.")
    return filing, None


@app.route("/api/v1/compliance/dashboard")
@role_required("business")
def dashboard():
    """The home page: the next deadline and how many filings are due, late or with a CA."""
    business = my_business()
    today = now()
    result = {"message": f"Welcome, {current_user().full_name}", "registered": business is not None,
              "next_deadline": None, "due_this_month": 0, "overdue": 0, "with_ca": 0}
    if business is None:
        return jsonify(result)
    for filing in ComplianceItem.query.filter_by(business_id=business.id).order_by(ComplianceItem.due_date):
        if filing.status in DONE:
            continue
        if filing.due_date < today:
            result["overdue"] += 1
        else:
            if result["next_deadline"] is None:
                result["next_deadline"] = filing_to_dict(filing)
            if (filing.due_date.year, filing.due_date.month) == (today.year, today.month):
                result["due_this_month"] += 1
        if filing.status == "with_ca":
            result["with_ca"] += 1
    return jsonify(result)


@app.route("/api/v1/compliance/items")
@role_required("business")
def list_filings():
    business = my_business()
    if business is None:
        return error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    filings = (ComplianceItem.query.filter_by(business_id=business.id)
               .order_by(ComplianceItem.due_date, ComplianceItem.form_code))
    return jsonify([filing_to_dict(filing) for filing in filings])


@app.route("/api/v1/compliance/items/<uuid:item_id>")
@role_required("business")
def get_filing(item_id):
    filing, problem = find_filing(item_id)
    return problem or jsonify(filing_page(filing))


@app.route("/api/v1/compliance/items/<uuid:item_id>/path", methods=["POST"])
@role_required("business")
def choose_path(item_id):
    """The business files it itself ("self") or with a CA ("ca")."""
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    path = (request.get_json(silent=True) or {}).get("path")
    if path not in ("self", "ca"):
        return error(422, "VALIDATION_ERROR", "Choose self or ca.")
    if filing.status not in NOT_STARTED:
        return error(409, "FILING_LOCKED", "This filing is already with a CA or filed.")
    filing.filing_path = path
    db.session.commit()
    return jsonify(filing_page(filing))


@app.route("/api/v1/compliance/items/<uuid:item_id>/checklist", methods=["POST"])
@role_required("business")
def tick_checklist(item_id):
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("ticked"), bool):
        return error(422, "VALIDATION_ERROR", "Send ticked as true or false.")
    if data.get("key") not in [entry["key"] for entry in checklist(filing.form_code)]:
        return error(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")
    set_tick(filing, data["key"], data["ticked"])
    db.session.commit()
    return jsonify(filing_page(filing))


@app.route("/api/v1/compliance/items/<uuid:item_id>/mark-filed", methods=["POST"])
@role_required("business")
def mark_filed(item_id):
    """The business filed it itself (with an optional ARN and acknowledgement file)."""
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    if filing.status == "with_ca":
        return error(409, "FILING_WITH_CA", "Your CA is handling this filing.")
    if filing.status not in NOT_STARTED:
        return error(409, "ALREADY_FILED", "This filing is already marked as filed.")
    user = current_user()
    problem = record_filed(filing, user.id, user, "self")
    if problem:
        return problem
    db.session.commit()
    return jsonify(filing_page(filing))


@app.route("/api/v1/compliance/items/<uuid:item_id>/unmark-filed", methods=["POST"])
@role_required("business")
def unmark_filed(item_id):
    """Undo a mistaken "mark as filed" (only for filings the business filed itself)."""
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    if filing.status not in DONE or filing.filing_path != "self":
        return error(409, "NOT_SELF_FILED", "Only a filing you marked as filed can be undone.")
    old_file = filing.acknowledgement_document_id
    filing.acknowledgement_document_id = filing.acknowledgement_no = filing.filed_at = filing.verified_at = None
    filing.status = "upcoming"
    if old_file:
        db.session.flush()  # the filing lets go of the file before the file is deleted
        remove_document(old_file)
    refresh_status(filing)
    db.session.commit()
    return jsonify(filing_page(filing))


@app.route("/api/v1/compliance/items/<uuid:item_id>/acknowledgement")
@role_required("business")
def download_acknowledgement(item_id):
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    if filing.acknowledgement_document_id is None:
        return error(404, "ACKNOWLEDGEMENT_MISSING", "No acknowledgement was uploaded.")
    return send_document(db.session.get(Document, filing.acknowledgement_document_id))


@app.route("/api/v1/compliance/items/<uuid:item_id>/peer-insights")
@role_required("business")
def peer_insights(item_id):
    """How businesses like this one file this form: by themselves or through a CA, and how
    often on time. "Like this one" = same entity type and MSME tier, shown only when at least
    10 of them filed it (fewer could point at one business); else all businesses; else none."""
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    business = db.session.get(Business, filing.business_id)
    profile = RegulatoryProfile.query.filter_by(business_id=business.id).first()
    tier = profile.msme_tier if profile else None
    result = {"form_code": filing.form_code, "scope": "none", "entity_type": business.entity_type,
              "msme_tier": tier, "min_businesses": 10, "business_count": 0, "filing_count": 0,
              "self": None, "ca": None}
    filed = ComplianceItem.query.filter(ComplianceItem.form_code == filing.form_code,
                                        ComplianceItem.status.in_(DONE), ComplianceItem.filed_at.isnot(None)).all()
    same_kind = set()  # the businesses with the same entity type and MSME tier
    for other in RegulatoryProfile.query.filter_by(msme_tier=tier):
        if db.session.get(Business, other.business_id).entity_type == business.entity_type:
            same_kind.add(other.business_id)
    for scope, group in (("segment", [f for f in filed if f.business_id in same_kind]), ("overall", filed)):
        businesses = {f.business_id for f in group}
        if len(businesses) < 10:
            continue
        result.update(scope=scope, business_count=len(businesses), filing_count=len(group))
        for path in ("self", "ca"):
            items = [f for f in group if f.filing_path == path]
            on_time = [f for f in items if date(f.filed_at) <= f.due_date]
            result[path] = {"count": len(items), "share_pct": round(len(items) * 100 / len(group)),
                            "on_time_pct": round(len(on_time) * 100 / len(items)) if items else None}
        break
    return jsonify(result)


# --- Penalties (late fees from penalty_rules; an empty amount means "not confirmed yet") ---


def estimate(filing, today, tax_due=None):
    """The late fee (and interest, with the tax due) of one filing today."""
    days_late = max((today - filing.due_date).days, 0)
    result = {"compliance_item_id": str(filing.id), "form_code": filing.form_code,
              "period_label": filing.period_label, "due_date": iso(filing.due_date), "days_late": days_late,
              "status": "pending", "late_fee": None, "interest": None, "total": None, "notes": [],
              "label": "Estimate (rules pending verification)"}
    if filing.status in DONE:
        result.update(status="filed", days_late=0)
        return result
    if days_late == 0:
        result["status"] = "not_late"
        return result
    rule = (PenaltyRule.query.filter(PenaltyRule.form_code == filing.form_code,
                                     PenaltyRule.effective_from <= filing.due_date)
            .order_by(PenaltyRule.effective_from.desc()).first())  # the rule on the due date
    if rule is None or (rule.effective_to and rule.effective_to <= filing.due_date):
        result["notes"].append("There is no penalty rule for this form yet.")
        return result
    if "TODO_VERIFY" not in rule.source_reference:
        result["label"] = "Estimate"
    late_fee = rule.flat_late_fee  # a flat fee, else days x the daily fee up to the cap
    if late_fee is None and rule.late_fee_per_day is not None:
        late_fee = rule.late_fee_per_day * days_late
        if rule.max_late_fee is not None:
            late_fee = min(late_fee, rule.max_late_fee)
    if late_fee is None:
        result["notes"].append("The late fee for this form is not confirmed yet.")
    interest = None
    if rule.annual_interest_rate is None:
        result["notes"].append("The interest rate is not confirmed yet.")
    elif tax_due is None:
        result["notes"].append("Enter the tax due to estimate the interest.")
    else:
        interest = tax_due * rule.annual_interest_rate / 100 * days_late / 365
    amounts = [amount for amount in (late_fee, interest) if amount is not None]
    if amounts:
        result.update(status="estimated", total=money(sum(amounts)))
    result.update(late_fee=money(late_fee), interest=money(interest))
    return result


@app.route("/api/v1/alerts/penalties")
@role_required("business")
def penalty_exposure():
    """The late fees of all overdue filings, for the dashboard (interest not included)."""
    business = my_business()
    if business is None:
        return error(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    today = now()
    items = []
    for filing in ComplianceItem.query.filter_by(business_id=business.id).order_by(ComplianceItem.due_date):
        if filing.status not in DONE and filing.due_date < today:
            items.append(estimate(filing, today))
    fees = [Decimal(item["late_fee"]) for item in items if item["late_fee"] is not None]
    verified = items and all(item["label"] == "Estimate" for item in items)
    return jsonify({"total_late_fees": money(sum(fees)), "overdue_count": len(items),
                    "estimated_count": len(fees), "pending_count": len(items) - len(fees),
                    "label": "Estimate" if verified else "Estimate (rules pending verification)",
                    "items": items})


@app.route("/api/v1/alerts/penalties/<uuid:item_id>")
@role_required("business")
def penalty_estimate(item_id):
    """One filing's late fee, and its interest when ?tax_due= (unpaid tax in rupees) is given."""
    filing, problem = find_filing(item_id)
    if problem:
        return problem
    tax_due = None
    if "tax_due" in request.args:
        tax_due = read_amount(request.args["tax_due"], 0, 10**10)
        if tax_due is None:
            return error(422, "VALIDATION_ERROR", "Enter the tax due in rupees.")
    return jsonify(estimate(filing, now(), tax_due))
