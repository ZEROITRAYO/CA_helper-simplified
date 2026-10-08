"""Registering a business, its regulatory profile, the NIC activity code and reading a
registration document to fill the form.

The profile is computed from legal thresholds stored in `rule_thresholds`; no legal
number is written in this file.
"""

import re

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from app import compliance, ocr
from app.models import (
    Business, EntityType, GstScheme, ItrForm, MsmeTier, NicCode, RegulatoryProfile, RuleThreshold,
    UserRole, db, today_in_india, utcnow,
)
from app.utils import (
    GST_STATES, MISSING, ApiError, current_business, current_user, format_inr, gstin_error,
    invalid, iso, json_body, money, read_amount, read_bool, read_choice, read_text, read_upload,
    roles_required, state_code,
)

bp = Blueprint("onboarding", __name__)

# Which version of the profile logic below produced a profile. Change it when the logic changes.
RULE_VERSION = "v2"  # v2: QRMP is the user's choice; the audit line is split in two

# Codes typed by people: stored in capitals, and an empty code counts as not given.
CODE_FORMATS = {
    "pan": (r"[A-Z]{5}[0-9]{4}[A-Z]", "Enter a valid PAN."),  # e.g. ABCDE1234F
    "gstin": (r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", "Enter a valid GSTIN."),  # 27ABCDE1234F1Z5
    "tan": (r"[A-Z]{4}[0-9]{5}[A-Z]", "Enter a valid TAN."),  # e.g. MUMA12345B
    "udyam_number": (r"UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}", "Enter a valid Udyam number."),
    "cin_llpin": (r".{1,21}", "Length must be between 1 and 21."),
}
COMPANY_TYPES = (EntityType.LLP, EntityType.PRIVATE_LIMITED)

# The profile lines compared in the "What changed" summary after an edit.
COMPARED_LINES = (
    "msme_tier", "gst_scheme", "itr_form", "presumptive_eligible", "audit_applicable",
    "other_audit_applicable", "files_24q", "files_26q",
)


# --- The registration form ---------------------------------------------------------------


def read_business_form(data):
    """Check the registration form and return the values. 422 VALIDATION_ERROR."""
    values = {
        "legal_name": read_text(data, "legal_name", 200),
        "address": read_text(data, "address", 500),
        "description": read_text(data, "description", 1000),
        "entity_type": read_choice(data, "entity_type", EntityType),
    }
    state = data.get("state")
    if state_code(state) is None:
        raise invalid("state", MISSING if state is None else "Choose your state from the list.")
    values["state"] = state
    for field in ("annual_turnover", "investment_amount"):
        values[field] = read_amount(data.get(field), 0, 9999999999)  # the column holds Numeric(12, 2)
        if values[field] is None:
            message = MISSING if data.get(field) is None else "Enter an amount from 0 to 9999999999."
            raise invalid(field, message)
    # Yes/no questions every business answers, and those that default to "no".
    for field in ("gst_registered", "deducts_tds", "pays_salary_above_limit"):
        values[field] = read_bool(data, field)
    for field in ("gst_composition", "gst_qrmp", "accounts_audited_other_law"):
        values[field] = read_bool(data, field, default=False)
    for field, (pattern, message) in CODE_FORMATS.items():
        code = data.get(field)
        if isinstance(code, str):
            code = code.strip().upper() or None
        if code is not None and (not isinstance(code, str) or not re.fullmatch(pattern, code)):
            raise invalid(field, message)
        values[field] = code
    if values["pan"] is None:
        raise invalid("pan", MISSING)
    phone = data.get("phone")
    if not isinstance(phone, str) or not re.fullmatch(r"[6-9][0-9]{9}", phone):  # an Indian mobile
        raise invalid("phone", MISSING if phone is None else "Enter a 10-digit mobile number.")
    values["phone"] = phone

    # Fields that are required only for some businesses.
    if values["gst_registered"] and not values["gstin"]:
        raise invalid("gstin", "Enter your GSTIN (you said you are GST registered).")
    if values["gst_composition"] and not values["gst_registered"]:
        raise invalid("gst_composition", "Only a GST-registered business can use composition.")
    if values["deducts_tds"] and not values["tan"]:
        raise invalid("tan", "Enter your TAN (you said you deduct TDS).")
    if values["entity_type"] in COMPANY_TYPES and not values["cin_llpin"]:
        raise invalid("cin_llpin", "Enter your CIN (company) or LLPIN (LLP).")
    if values["gst_registered"]:
        problem = gstin_error(values["gstin"], values["pan"], values["state"])
        if problem:
            raise invalid("gstin", problem)

    # Forget values that do not apply, e.g. a GSTIN sent with gst_registered = false.
    if not values["gst_registered"]:
        values["gstin"] = None
    if not values["deducts_tds"]:
        values["tan"] = None
    if not values["gst_registered"] or values["gst_composition"]:
        values["gst_qrmp"] = False
    if values["entity_type"] not in (EntityType.PARTNERSHIP, EntityType.LLP):
        values["accounts_audited_other_law"] = False
    if values["entity_type"] not in COMPANY_TYPES:
        values["cin_llpin"] = None
    return values


def business_page(business):
    """{business, profile, nic_code}: what the business page shows."""
    fields = (
        "legal_name", "entity_type", "state", "address", "description", "pan", "phone",
        "gst_registered", "gstin", "gst_composition", "gst_qrmp", "accounts_audited_other_law",
        "deducts_tds", "tan", "pays_salary_above_limit", "cin_llpin", "udyam_number",
    )
    page_business = {"id": str(business.id)}
    for field in fields:
        page_business[field] = getattr(business, field)
    page_business["annual_turnover"] = money(business.annual_turnover)
    page_business["investment_amount"] = money(business.investment_amount)
    # A state typed before the state list existed: the form asks for it again.
    page_business["state_needs_review"] = state_code(business.state) is None

    profile = db.session.scalar(select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id))
    page_profile = None
    if profile is not None:
        page_profile = {line: getattr(profile, line) for line in COMPARED_LINES}
        page_profile.update(
            gst_registration_suggested=profile.gst_registration_suggested,
            roc_not_tracked=profile.roc_not_tracked, explanations=profile.explanations,
            rule_version=profile.rule_version, computed_at=iso(profile.computed_at),
        )
    nic = db.session.get(NicCode, business.nic_code_id) if business.nic_code_id else None
    return {
        "business": page_business, "profile": page_profile,
        "nic_code": {"code": nic.code, "description": nic.description} if nic else None,
    }


# --- The regulatory profile --------------------------------------------------------------


def get_threshold(key, today):
    """The legal value `key` in force today (latest effective_from)."""
    row = db.session.scalar(
        select(RuleThreshold).where(RuleThreshold.key == key, RuleThreshold.effective_from <= today)
        .order_by(RuleThreshold.effective_from.desc())
    )
    if row is None:
        raise ApiError(500, "RULE_MISSING", f"The rule '{key}' is missing. Run `flask seed`.")
    return row.value


def compute_profile(business, today):
    """Work out the business's regulatory profile."""
    turnover = business.annual_turnover
    entity = business.entity_type

    # 1. MSME tier: the smallest tier whose investment AND turnover limits both fit.
    msme_tier = MsmeTier.NOT_MSME
    for tier in (MsmeTier.MEDIUM, MsmeTier.SMALL, MsmeTier.MICRO):
        if (business.investment_amount <= get_threshold(f"msme.{tier}.max_investment", today)
                and turnover <= get_threshold(f"msme.{tier}.max_turnover", today)):
            msme_tier = tier

    # 2. GST scheme. A business that is not registered but above the limit is told to ask a CA.
    registration_limit = get_threshold("gst.registration.min_turnover", today)
    gst_registration_suggested = not business.gst_registered and turnover > registration_limit
    if not business.gst_registered:
        gst_scheme = GstScheme.NOT_REGISTERED
    elif business.gst_composition and turnover <= get_threshold("gst.composition.max_turnover", today):
        gst_scheme = GstScheme.COMPOSITION
    elif business.gst_qrmp and turnover <= get_threshold("gst.qrmp.max_turnover", today):
        gst_scheme = GstScheme.REGULAR_QRMP
    else:  # monthly returns: chosen, or quarterly (QRMP) is not allowed above the limit
        gst_scheme = GstScheme.REGULAR_MONTHLY

    # 3. Presumptive scheme (section 44AD; section 58 of the 2025 Act): individuals, proprietors
    #    and partnership firms.
    presumptive_eligible = (
        entity not in COMPANY_TYPES and turnover <= get_threshold("itr.presumptive_44ad.max_turnover", today)
    )
    # 4. Audits (either one moves the ITR due date later).
    # 4a. Tax audit under section 44AB (section 63 of the 2025 Act), from turnover; none
    #     with the presumptive scheme.
    audit_applicable = (
        not presumptive_eligible and turnover > get_threshold("itr.audit_44ab.min_turnover", today)
    )
    # 4b. Accounts audited under another law: companies always; partnerships and LLPs
    # answer the question on the form (whether it applies depends on their own rules).
    other_audit_applicable = entity == EntityType.PRIVATE_LIMITED or (
        entity in (EntityType.PARTNERSHIP, EntityType.LLP) and business.accounts_audited_other_law
    )

    # 5. ITR form.
    if entity == EntityType.PRIVATE_LIMITED:
        itr_form = ItrForm.ITR_6
    elif entity == EntityType.LLP:
        itr_form = ItrForm.ITR_5
    elif presumptive_eligible:
        itr_form = ItrForm.ITR_4
    elif entity == EntityType.PARTNERSHIP:
        itr_form = ItrForm.ITR_5
    else:
        itr_form = ItrForm.ITR_3

    # 7. ROC/MCA filings are out of scope; LLPs and companies get a notice.
    roc_not_tracked = entity in COMPANY_TYPES
    explanations = {
        "gst_scheme": (
            f"Not registered, but turnover is above {format_inr(registration_limit)}: "
            "you may need GST registration. Ask a CA." if gst_registration_suggested else ""
        ),
        "roc_not_tracked": (
            "LLPs and companies also have ROC/MCA filings, which this app does not track."
            if roc_not_tracked else ""
        ),
    }
    return {
        "msme_tier": msme_tier, "gst_scheme": gst_scheme,
        "gst_registration_suggested": gst_registration_suggested, "itr_form": itr_form,
        "presumptive_eligible": presumptive_eligible, "audit_applicable": audit_applicable,
        "other_audit_applicable": other_audit_applicable,
        # 6. TDS returns.
        "files_24q": business.deducts_tds and business.pays_salary_above_limit,
        "files_26q": business.deducts_tds,
        "roc_not_tracked": roc_not_tracked, "explanations": explanations, "rule_version": RULE_VERSION,
    }


def resync_all_filings(today=None):
    """Match every business's filings to the current rules (run by `flask seed`)."""
    for profile in db.session.scalars(select(RegulatoryProfile)):
        compliance.sync_filings(profile.business_id, profile, today or today_in_india())


# --- Routes ------------------------------------------------------------------------------


@bp.post("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def register_business():
    """Save the business, compute its profile and create this year's filings."""
    values = read_business_form(json_body())
    if current_business(required=False):
        raise ApiError(409, "BUSINESS_EXISTS", "You have already registered your business.")
    business = Business(user_id=current_user().id, **values)
    db.session.add(business)
    db.session.flush()  # gives business.id
    today = today_in_india()
    profile = RegulatoryProfile(business_id=business.id, computed_at=utcnow(),
                                **compute_profile(business, today))
    db.session.add(profile)
    compliance.sync_filings(business.id, profile, today)
    db.session.commit()
    return jsonify(business_page(business)), 201


@bp.get("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def get_business_page():
    return jsonify(business_page(current_business()))


@bp.put("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def update_business():
    """Save the edited form, recompute the profile and sync the filings."""
    business = current_business()
    for field, value in read_business_form(json_body()).items():
        setattr(business, field, value)
    today = today_in_india()
    profile = db.session.scalar(select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id))
    old = {line: getattr(profile, line) for line in COMPARED_LINES}
    for field, value in compute_profile(business, today).items():
        setattr(profile, field, value)
    profile.computed_at = utcnow()
    filings = compliance.sync_filings(business.id, profile, today)
    db.session.commit()
    page = business_page(business)
    changed = [
        {"line": line, "old": old[line], "new": getattr(profile, line)}
        for line in COMPARED_LINES if getattr(profile, line) != old[line]
    ]
    page["changes"] = {"profile": changed, "filings": filings}
    return jsonify(page)


@bp.get("/onboarding/nic-codes")
@roles_required(UserRole.BUSINESS)
def search_nic_codes():
    """Up to 20 codes whose code or description contains `q` (choosing a code by hand)."""
    query = request.args.get("q", "").strip()[:100]
    if len(query) < 2:
        return jsonify([])
    pattern = f"%{query}%"
    stmt = select(NicCode).where(or_(NicCode.code.ilike(pattern), NicCode.description.ilike(pattern)))
    return jsonify([
        {"code": nic.code, "description": nic.description}
        for nic in db.session.scalars(stmt.order_by(NicCode.code).limit(20))
    ])


@bp.put("/onboarding/business/nic-code")
@roles_required(UserRole.BUSINESS)
def set_nic_code():
    """Save the NIC code the user confirmed. 422 UNKNOWN_NIC_CODE if it is not in the list."""
    code = read_text(json_body(), "code", 10)
    business = current_business()
    nic = db.session.scalar(select(NicCode).where(NicCode.code == code))
    if nic is None:
        raise ApiError(422, "UNKNOWN_NIC_CODE", "Choose a code from the NIC list.")
    business.nic_code_id = nic.id
    db.session.commit()
    return jsonify({"code": nic.code, "description": nic.description})


@bp.get("/onboarding/states")
@roles_required(UserRole.BUSINESS)
def list_states():
    """The states and union territories with their GST codes, for the form."""
    return jsonify([{"name": state["name"], "code": state["code"]} for state in GST_STATES])


@bp.post("/onboarding/autofill")
@roles_required(UserRole.BUSINESS)
def autofill():
    """Suggest form values from a GST certificate or PAN card (read in memory only)."""
    upload, data = read_upload()
    try:
        text = ocr.extract_text(data, upload.mimetype)
    except ocr.OcrError as error:
        raise ApiError(422, "DOCUMENT_UNREADABLE", f"We could not read this file. {error}") from error
    return jsonify({"found": ocr.read_registration(text)})
