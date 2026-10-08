"""Filings: which forms a business must file and when, the calendar, the filing page
(checklist, path, mark filed), the dashboard numbers, peer insights and the overdue job.

Each row of `obligation_templates` says which businesses a form applies to
(`applicability`, matched against the regulatory profile) and when it is due
(`due_date_rule`). The rows are data, seeded in app/seed.py; no legal date is written
in this file.
"""

import calendar
import re
from datetime import date
from zoneinfo import ZoneInfo

import yaml
from flask import Blueprint, jsonify, request
from sqlalchemy import delete, or_, select

from app import documents
from app.models import (
    Business, ChecklistTick, ComplianceItem, ComplianceItemDocument, ComplianceStatus, DocumentRequest,
    DocumentType, Engagement, EngagementItem, EngagementStatus, FilingPath, FormCode, Frequency,
    ObligationTemplate, RegulatoryProfile, ReminderLog, UserRole, db, today_in_india, utcnow,
)
from app.utils import (
    REPO_ROOT, ApiError, current_business, current_user, invalid, iso, json_body, read_bool,
    read_choice, read_text, roles_required,
)

bp = Blueprint("compliance", __name__)

# Filings in these states are done; a profile change never removes them.
DONE_STATUSES = (ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED)
# Filings the business itself can still work on: choose a path, mark filed.
SELF_FILEABLE_STATUSES = (
    ComplianceStatus.UPCOMING, ComplianceStatus.DOCS_PENDING, ComplianceStatus.READY,
    ComplianceStatus.OVERDUE,
)

# A group's peer figures are shown only when at least this many businesses have filed the
# form (fewer would say little and could point at one business). A product rule.
MIN_PEER_BUSINESSES = 10


def filing_to_dict(filing):
    """One filing, e.g. GSTR-3B for Apr 2026, due 2026-05-20, with its filing details."""
    return {
        "id": str(filing.id), "form_code": filing.form_code, "fy": filing.fy,
        "period_label": filing.period_label, "period_start": iso(filing.period_start),
        "period_end": iso(filing.period_end), "due_date": iso(filing.due_date),
        "status": filing.status, "filing_path": filing.filing_path,
        "filed_at": iso(filing.filed_at), "acknowledgement_no": filing.acknowledgement_no,
    }


# --- Periods and due dates ---------------------------------------------------------------


def financial_year_start(day):
    """1 April of the financial year that `day` falls in (a financial year runs April to March)."""
    return date(day.year if day.month >= 4 else day.year - 1, 4, 1)


def fy_label(fy_start):
    """The financial year's name, e.g. "2026-27" for 1 April 2026 to 31 March 2027."""
    return f"{fy_start.year}-{str(fy_start.year + 1)[2:]}"


def periods_of_year(frequency, fy_start):
    """The (label, start, end, quarter) periods of one financial year."""
    fy = fy_label(fy_start)
    if frequency == Frequency.YEARLY:
        return [(f"FY {fy}", fy_start, date(fy_start.year + 1, 3, 31), None)]
    months_per_period = 1 if frequency == Frequency.MONTHLY else 3
    periods = []
    for number in range(1, 12 // months_per_period + 1):
        # Months counted from January of the FY's first year: 3 = April, 12 = next January.
        first = (number - 1) * months_per_period + 3
        start = date(fy_start.year + first // 12, first % 12 + 1, 1)
        last = first + months_per_period - 1
        year, month = fy_start.year + last // 12, last % 12 + 1
        end = date(year, month, calendar.monthrange(year, month)[1])
        if frequency == Frequency.MONTHLY:
            periods.append((start.strftime("%b %Y"), start, end, None))  # "Apr 2026"
        else:
            periods.append((f"Q{number} {fy}", start, end, number))  # "Q1 2026-27"
    return periods


def due_date(template, period_end, quarter=None, audit=False, itr_form=None):
    """When the filing for the period ending on `period_end` is due, from the template's rule.

    monthly    {"day": 11}                    the 11th of the month after the period
    quarterly  {"quarters": [[7, 13], ...]}   [month, day] for Q1..Q4, after the quarter ends
    yearly     {"month": 7, "day": 31}        that date after the financial year ends;
               "audit_month"/"audit_day"      used instead when the business has an audit;
               "by_itr_form": {"itr_5": [7, 31]}   used instead, without an audit, for a
                                              business whose profile has that ITR form
    """
    rule = template.due_date_rule
    if template.frequency == Frequency.MONTHLY:
        month, day = period_end.month % 12 + 1, rule["day"]  # December (12) -> January (1)
    elif template.frequency == Frequency.QUARTERLY:
        month, day = rule["quarters"][quarter - 1]
    elif audit and "audit_month" in rule:
        month, day = rule["audit_month"], rule["audit_day"]
    else:
        month, day = rule.get("by_itr_form", {}).get(itr_form, (rule["month"], rule["day"]))
    # The first date with this month and day that comes after the period's end.
    candidate = date(period_end.year, month, day)
    return candidate if candidate > period_end else date(period_end.year + 1, month, day)


def open_filing_ids(filing_ids):
    """The filings among `filing_ids` in an open (requested or active) engagement."""
    stmt = select(EngagementItem.compliance_item_id).join(Engagement).where(
        EngagementItem.compliance_item_id.in_(filing_ids),
        Engagement.status.in_([EngagementStatus.REQUESTED, EngagementStatus.ACTIVE]),
    )
    return set(db.session.scalars(stmt))


def sync_filings(business_id, profile, today):
    """Make the business's filings of the current financial year match its profile.
    Returns {"added", "removed", "kept_with_ca"} counts.

    - Every applicable form and period gets a filing, from 1 April: periods whose due
      date has passed start as "overdue" (the business may have filed them before it
      joined; it can mark them filed).
    - A filing that no longer applies is deleted, unless it is filed, with a CA
      (status "with_ca") or in an open engagement.
    - A not-started filing gets the current period and due date: the audit answer moves
      the ITR date; switching between monthly and quarterly returns turns "Q1" into "Apr"
      (both start on 1 April, and there is one filing per form and start date).
    """
    fy_start = financial_year_start(today)
    fy = fy_label(fy_start)
    audit = bool(profile.audit_applicable or profile.other_audit_applicable)
    templates = db.session.scalars(select(ObligationTemplate).where(
        ObligationTemplate.effective_from <= today,
        or_(ObligationTemplate.effective_to.is_(None), ObligationTemplate.effective_to > today),
    ))
    # {(form_code, period_start): (template, label, start, end, due date)} for this FY.
    wanted = {}
    for template in templates:
        # Every condition of the template must match the profile ({} matches all).
        if all(getattr(profile, field) in values for field, values in template.applicability.items()):
            for label, start, end, quarter in periods_of_year(template.frequency, fy_start):
                due = due_date(template, end, quarter, audit, profile.itr_form)
                wanted[(template.form_code, start)] = (template, label, start, end, due)

    existing = {}
    for item in db.session.scalars(select(ComplianceItem).where(
        ComplianceItem.business_id == business_id, ComplianceItem.fy == fy
    )):
        existing[(item.form_code, item.period_start)] = item
    keep = open_filing_ids([item.id for item in existing.values()])

    counts = {"added": 0, "removed": 0, "kept_with_ca": 0}
    for key, (template, label, start, end, due) in wanted.items():
        status = ComplianceStatus.OVERDUE if due < today else ComplianceStatus.UPCOMING
        item = existing.get(key)
        if item is None:
            db.session.add(ComplianceItem(
                business_id=business_id, template_id=template.id, form_code=template.form_code,
                fy=fy, period_label=label, period_start=start, period_end=end, due_date=due,
                status=status,
            ))
            counts["added"] += 1
            continue
        item.template_id = template.id  # the rule row in force now
        not_started = item.status in (ComplianceStatus.UPCOMING, ComplianceStatus.OVERDUE)
        if not_started and (item.period_end, item.due_date) != (end, due):
            item.period_label, item.period_end, item.due_date, item.status = label, end, due, status

    for key, item in existing.items():
        if key in wanted or item.status in DONE_STATUSES:
            continue
        if item.status == ComplianceStatus.WITH_CA or item.id in keep:
            counts["kept_with_ca"] += 1
            continue
        # Delete the filing and the rows that point to it (its files stay in the vault).
        for model in (ChecklistTick, ComplianceItemDocument, ReminderLog, DocumentRequest, EngagementItem):
            db.session.execute(delete(model).where(model.compliance_item_id == item.id))
        db.session.delete(item)
        counts["removed"] += 1
    return counts


def list_filings(business):
    """The business's filings, soonest due first."""
    return db.session.scalars(
        select(ComplianceItem).where(ComplianceItem.business_id == business.id)
        .order_by(ComplianceItem.due_date, ComplianceItem.form_code)
    ).all()


def get_filings_by_ids(filing_ids):
    """{id: ComplianceItem} for the filings among `filing_ids`."""
    stmt = select(ComplianceItem).where(ComplianceItem.id.in_(filing_ids))
    return {filing.id: filing for filing in db.session.scalars(stmt)}


def own_filing(business, item_id):
    """One filing of this business. 404 FILING_NOT_FOUND for anyone else's."""
    filing = db.session.get(ComplianceItem, item_id)
    if filing is None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    return filing


# --- Form content ------------------------------------------------------------------------
# Every form has a folder of human-written files (content/README.md):
#   explanation.md, instructions.md  Markdown with a small front matter block (form, status)
#   checklist.yaml                   the documents to have ready: key, label, required, help

CONTENT_DIR = REPO_ROOT / "content" / "forms"
FORM_FOLDERS = {
    FormCode.ITR: "ITR", FormCode.GSTR_1: "GSTR-1", FormCode.GSTR_3B: "GSTR-3B",
    FormCode.CMP_08: "CMP-08", FormCode.GSTR_4: "GSTR-4", FormCode.TDS_24Q: "24Q",
    FormCode.TDS_26Q: "26Q",
}


def checklist(form_code):
    """The form's checklist entries: [{key, label, required, help}]."""
    data = yaml.safe_load((CONTENT_DIR / FORM_FOLDERS[form_code] / "checklist.yaml").read_text())
    return [
        {"key": item["key"], "label": item["label"], "required": bool(item.get("required", False)),
         "help": item.get("help")}
        for item in data.get("items") or []
    ]


def get_form_content(form_code):
    """A form's explanation, instructions and checklist."""
    form_code = FormCode(form_code)
    result = {"form_code": form_code, "status": "DONE", "checklist": checklist(form_code)}
    for page in ("explanation", "instructions"):
        # A page without its front matter (form, status) and its writers' comments.
        text = (CONTENT_DIR / FORM_FOLDERS[form_code] / f"{page}.md").read_text(encoding="utf-8")
        status = "TODO"
        if text.startswith("---"):
            _, front_matter, text = text.split("---", 2)
            status = (yaml.safe_load(front_matter) or {}).get("status", "TODO")
        result[page] = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
        if status == "TODO" or (status == "DRAFT" and result["status"] == "DONE"):
            result["status"] = status
    return result


# --- The checklist and the filing page ----------------------------------------------------


def checklist_with_ticks(filing):
    """The form's checklist entries, each with `ticked`: [{key, label, required, help, ticked}]."""
    ticked = set(db.session.scalars(
        select(ChecklistTick.checklist_key).where(ChecklistTick.compliance_item_id == filing.id)
    ))
    return [{**entry, "ticked": entry["key"] in ticked} for entry in checklist(filing.form_code)]


def missing_documents(filing):
    """The labels of the required checklist entries not ticked yet."""
    return [e["label"] for e in checklist_with_ticks(filing) if e["required"] and not e["ticked"]]


def refresh_status(filing, today):
    """Work out a not-started filing's status again.

    Past its due date: overdue. Otherwise from the checklist: nothing ticked yet ->
    upcoming; some ticked but a required document missing -> docs pending; every
    required document ticked -> ready. With a CA, filed and verified filings keep
    their status.
    """
    if filing.status not in SELF_FILEABLE_STATUSES:
        return
    if filing.due_date < today:
        filing.status = ComplianceStatus.OVERDUE
    elif not any(entry["ticked"] for entry in checklist_with_ticks(filing)):
        filing.status = ComplianceStatus.UPCOMING
    elif missing_documents(filing):
        filing.status = ComplianceStatus.DOCS_PENDING
    else:
        filing.status = ComplianceStatus.READY


def set_tick(filing, key, ticked):
    """Add or remove a tick and update the status. 422 UNKNOWN_CHECKLIST_KEY."""
    if key not in [entry["key"] for entry in checklist(filing.form_code)]:
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")
    existing = db.session.scalar(select(ChecklistTick).where(
        ChecklistTick.compliance_item_id == filing.id, ChecklistTick.checklist_key == key
    ))
    if ticked and existing is None:
        db.session.add(ChecklistTick(compliance_item_id=filing.id, checklist_key=key))
    if not ticked and existing is not None:
        db.session.delete(existing)
    db.session.flush()  # so refresh_status sees the change
    refresh_status(filing, today_in_india())


def filing_page(filing):
    """Everything the filing page shows: dates, status, texts, checklist, acknowledgement."""
    content = get_form_content(filing.form_code)
    acknowledgement = None
    if filing.acknowledgement_document_id is not None:
        # Only the stored metadata: the file itself is not opened for the page.
        document = documents.get_document(filing.acknowledgement_document_id)
        acknowledgement = {
            "filename": document.original_filename,
            "uploaded_at": iso(document.created_at),
            # Why it is (not) verified, from the fields OCR read when it was uploaded.
            "verification": documents.verify_acknowledgement(document, filing),
        }
    # The form's name on its page, e.g. "GSTR-3B (quarterly, QRMP)".
    renamed = RENAMED_FORMS.get(filing.form_code)
    if renamed is not None and filing.fy >= renamed[0]:
        form_name_shown = renamed[2]
    else:
        form_name_shown = db.session.get(ObligationTemplate, filing.template_id).name
    return {
        "filing": filing_to_dict(filing), "form_name": form_name_shown,
        "content_status": content["status"], "explanation": content["explanation"],
        "instructions": content["instructions"], "checklist": checklist_with_ticks(filing),
        "acknowledgement": acknowledgement,
    }


def read_acknowledgement_no():
    """The optional ARN of a mark-filed form (up to 50 characters), in capitals."""
    number = request.form.get("acknowledgement_no")
    if number is not None and len(number) > 50:
        raise invalid("acknowledgement_no", "Longer than maximum length 50.", "form")
    return (number or "").strip().upper() or None


def record_filed(filing, owner_id, uploader, path):
    """Mark it filed with the form's ARN and file; a matching acknowledgement verifies it."""
    acknowledgement_no = read_acknowledgement_no()
    document = None
    if "file" in request.files:  # stored first: a refused file changes nothing
        document = documents.add_document(owner_id, uploader.id, DocumentType.ACKNOWLEDGEMENT)
        document.fy, document.period_label = filing.fy, filing.period_label
        filing.acknowledgement_document_id = document.id
    filing.status = ComplianceStatus.FILED
    filing.filing_path = path
    filing.filed_at = utcnow()
    filing.acknowledgement_no = acknowledgement_no
    if document is None:
        return
    result = documents.verify_acknowledgement(document, filing)
    if result["verified"]:
        filing.status = ComplianceStatus.FILED_VERIFIED
        filing.verified_at = utcnow()
        filing.acknowledgement_no = filing.acknowledgement_no or result["acknowledgement_no"]


# --- The overdue job (run by the worker) -------------------------------------------------

# The business still has to act on filings in these states, so they turn "overdue" once
# the due date has passed. A filing "With CA" keeps that status: the CA is handling it,
# and the pages already show how late it is from its due date. Filed ones are done.
NOT_STARTED_STATUSES = (ComplianceStatus.UPCOMING, ComplianceStatus.DOCS_PENDING, ComplianceStatus.READY)


def mark_overdue_filings(today=None):
    """Mark not-started filings past their due date "overdue"; returns how many."""
    late = db.session.scalars(select(ComplianceItem).where(
        ComplianceItem.status.in_(NOT_STARTED_STATUSES),
        ComplianceItem.due_date < (today or today_in_india()),
    )).all()
    for filing in late:
        filing.status = ComplianceStatus.OVERDUE
    db.session.commit()
    return len(late)


# --- Forms renamed by law (display names only) ------------------------------------------

# From the first financial year given, a form is shown under its new name; its code, content
# folder and rules stay. The Income-tax Act, 2025 and the Income-tax Rules, 2026 renamed the
# quarterly TDS statements from tax year 2026-27: 24Q is Form 138 and 26Q is Form 140
# (incometax.gov.in, Form 138 / Form 140 user manuals). frontend/src/lib/labels.js
# (RENAMED_FORMS) has the same list.
RENAMED_FORMS = {
    FormCode.TDS_24Q: ("2026-27", "Form 138 (earlier 24Q)", "TDS return, salary (Form 138, earlier 24Q)"),
    FormCode.TDS_26Q: (
        "2026-27", "Form 140 (earlier 26Q)", "TDS return, other payments (Form 140, earlier 26Q)"
    ),
}


def form_name(form_code, fy):
    """The form's short name for financial year `fy`, e.g. "Form 138 (earlier 24Q)"."""
    renamed = RENAMED_FORMS.get(form_code)
    if renamed is not None and fy >= renamed[0]:
        return renamed[1]
    return FORM_FOLDERS[form_code]


def filing_name(filing):
    """e.g. "GSTR-3B (Q1 2026-27)" or "Form 138 (earlier 24Q) (Q2 2026-27)", for messages."""
    return f"{form_name(filing.form_code, filing.fy)} ({filing.period_label})"


# --- Peer insights and the admin's numbers --------------------------------------------


def filed_on_time(filing):
    """Filed on or before its due date, in Indian time."""
    return filing.filed_at.astimezone(ZoneInfo("Asia/Kolkata")).date() <= filing.due_date


def peer_insights(business, filing):
    """How businesses like this one file this form: the share filed by the business itself
    and through a CA, and how often each path was on time.

    The group is the businesses with the same entity type and MSME tier ("segment"), shown
    only when at least MIN_PEER_BUSINESSES of them filed the form; otherwise every business
    ("overall"), or nothing ("none") when even those are too few.
    """
    profile = db.session.scalar(select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id))
    tier = profile.msme_tier if profile else None
    result = {
        "form_code": filing.form_code, "scope": "none", "entity_type": business.entity_type,
        "msme_tier": tier, "min_businesses": MIN_PEER_BUSINESSES, "business_count": 0,
        "filing_count": 0, "self": None, "ca": None,
    }
    # The segment: the businesses with the same entity type and MSME tier.
    segment = select(Business.id).join(RegulatoryProfile, RegulatoryProfile.business_id == Business.id).where(
        Business.entity_type == business.entity_type, RegulatoryProfile.msme_tier == tier
    )
    for scope in ("segment", "overall") if tier else ("overall",):
        stmt = select(ComplianceItem).where(
            ComplianceItem.form_code == filing.form_code,
            ComplianceItem.status.in_(DONE_STATUSES), ComplianceItem.filed_at.is_not(None),
        )
        if scope == "segment":
            stmt = stmt.where(ComplianceItem.business_id.in_(segment))
        filed = list(db.session.scalars(stmt))
        businesses = {item.business_id for item in filed}
        if len(businesses) < MIN_PEER_BUSINESSES:
            continue
        paths = {path: [item for item in filed if item.filing_path == path] for path in ("self", "ca")}
        total = len(paths["self"]) + len(paths["ca"])
        result.update(scope=scope, business_count=len(businesses), filing_count=total)
        for name, items in paths.items():
            on_time = sum(1 for item in items if filed_on_time(item))
            result[name] = {
                "count": len(items),
                "share_pct": round(len(items) * 100 / total) if total else None,
                "on_time_pct": round(on_time * 100 / len(items)) if items else None,
            }
        break
    return result


def filing_stats(today=None):
    """For the admin: live filings by status and the overdue rate in percent."""
    today = today or today_in_india()
    by_status = {status.value: 0 for status in ComplianceStatus}
    due = late = 0
    for filing in db.session.scalars(select(ComplianceItem)):
        by_status[filing.status] += 1
        if filing.due_date < today:
            due += 1
            done = filing.status in DONE_STATUSES and filing.filed_at is not None
            if not done or not filed_on_time(filing):
                late += 1
    return {
        "filings_by_status": by_status, "filings_due_so_far": due, "filings_late": late,
        "overdue_rate": round(late * 100 / due, 1) if due else None,
    }


# --- Routes ------------------------------------------------------------------------------


@bp.get("/compliance/dashboard")
@roles_required(UserRole.BUSINESS)
def dashboard():
    """The business home page: a welcome, the next deadline and three counts (just the
    welcome before registering)."""
    business = current_business(required=False)
    today = today_in_india()
    result = {
        "message": f"Welcome, {current_user().full_name}", "registered": business is not None,
        "next_deadline": None, "due_this_month": 0, "overdue": 0, "with_ca": 0,
    }
    filings = list_filings(business) if business else []
    for filing in filings:  # soonest due first
        if filing.status in DONE_STATUSES:
            continue
        if filing.due_date < today:
            result["overdue"] += 1
        else:
            if result["next_deadline"] is None:
                result["next_deadline"] = filing_to_dict(filing)
            if (filing.due_date.year, filing.due_date.month) == (today.year, today.month):
                result["due_this_month"] += 1
        if filing.status == ComplianceStatus.WITH_CA:
            result["with_ca"] += 1
    return jsonify(result)


@bp.get("/compliance/items")
@roles_required(UserRole.BUSINESS)
def list_items():
    """The business's filings, soonest due first."""
    return jsonify([filing_to_dict(filing) for filing in list_filings(current_business())])


@bp.get("/compliance/items/<uuid:item_id>")
@roles_required(UserRole.BUSINESS)
def get_item(item_id):
    return jsonify(filing_page(own_filing(current_business(), item_id)))


@bp.post("/compliance/items/<uuid:item_id>/path")
@roles_required(UserRole.BUSINESS)
def choose_path(item_id):
    """The business files it itself ("self") or with a CA ("ca")."""
    path = read_choice(json_body(), "path", FilingPath)
    filing = own_filing(current_business(), item_id)
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already with a CA or filed.")
    filing.filing_path = path
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/checklist")
@roles_required(UserRole.BUSINESS)
def tick_checklist(item_id):
    """Tick or untick one document of the checklist; the status follows."""
    data = json_body()
    key, ticked = read_text(data, "key", 50), read_bool(data, "ticked")
    filing = own_filing(current_business(), item_id)
    set_tick(filing, key, ticked)
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/mark-filed")
@roles_required(UserRole.BUSINESS)
def mark_filed(item_id):
    """The business filed it itself: an optional ARN and acknowledgement file."""
    user = current_user()
    filing = own_filing(current_business(), item_id)
    if filing.status == ComplianceStatus.WITH_CA:
        raise ApiError(409, "FILING_WITH_CA", "Your CA is handling this filing.")
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "ALREADY_FILED", "This filing is already marked as filed.")
    record_filed(filing, user.id, user, FilingPath.SELF)
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/unmark-filed")
@roles_required(UserRole.BUSINESS)
def unmark_filed(item_id):
    """Undo a mistaken "mark as filed" of a filing the business marked itself."""
    filing = own_filing(current_business(), item_id)
    if filing.status not in DONE_STATUSES or filing.filing_path != FilingPath.SELF:
        raise ApiError(409, "NOT_SELF_FILED", "Only a filing you marked as filed can be undone.")
    old_document_id = filing.acknowledgement_document_id
    filing.acknowledgement_document_id = filing.acknowledgement_no = None
    filing.filed_at = filing.verified_at = None
    filing.status = ComplianceStatus.UPCOMING
    if old_document_id is not None:
        db.session.flush()  # the filing lets go of the file before the file is deleted
        documents.remove_document(old_document_id)
    refresh_status(filing, today_in_india())
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.get("/compliance/items/<uuid:item_id>/acknowledgement")
@roles_required(UserRole.BUSINESS)
def get_acknowledgement(item_id):
    """The acknowledgement file the business uploaded."""
    filing = own_filing(current_business(), item_id)
    if filing.acknowledgement_document_id is None:
        raise ApiError(404, "ACKNOWLEDGEMENT_MISSING", "No acknowledgement was uploaded.")
    return documents.send_document(documents.get_document(filing.acknowledgement_document_id))


@bp.get("/compliance/items/<uuid:item_id>/peer-insights")
@roles_required(UserRole.BUSINESS)
def get_peer_insights(item_id):
    business = current_business()
    return jsonify(peer_insights(business, own_filing(business, item_id)))
