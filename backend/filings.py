# Everything about filings that several route files need: periods and due dates, making a
# business's calendar, the checklists and texts of each form, the filing page, and checking
# an uploaded acknowledgement. The legal dates come from obligation_templates (seed.py).

import calendar
import re
from datetime import date

import yaml
from flask import request

from helpers import REPO, error, iso, read_upload, save_document, today_in_india
from models import (
    ChecklistTick, ComplianceItem, ComplianceItemDocument, Document, DocumentRequest, Engagement,
    EngagementItem, ObligationTemplate, ReminderLog, db, now,
)

DONE = ("filed", "filed_verified")  # a filed filing never changes again
NOT_STARTED = ("upcoming", "docs_pending", "ready", "overdue")  # the business can still work on these

FORM_FOLDERS = {"itr": "ITR", "gstr_1": "GSTR-1", "gstr_3b": "GSTR-3B", "cmp_08": "CMP-08",
                "gstr_4": "GSTR-4", "tds_24q": "24Q", "tds_26q": "26Q"}

# From tax year 2026-27 the TDS returns 24Q and 26Q are called Form 138 and Form 140
# (Income-tax Act 2025). frontend/src/lib.js has the same list.
RENAMED_FORMS = {
    "tds_24q": ("2026-27", "Form 138 (earlier 24Q)", "TDS return, salary (Form 138, earlier 24Q)"),
    "tds_26q": ("2026-27", "Form 140 (earlier 26Q)", "TDS return, other payments (Form 140, earlier 26Q)"),
}


def form_name(form_code, fy):
    """The form's short name in that financial year, e.g. "GSTR-3B" or "Form 138 (earlier 24Q)"."""
    if form_code in RENAMED_FORMS and fy >= RENAMED_FORMS[form_code][0]:
        return RENAMED_FORMS[form_code][1]
    return FORM_FOLDERS[form_code]


def filing_name(filing):
    """e.g. "GSTR-3B (Q1 2026-27)", for messages."""
    return f"{form_name(filing.form_code, filing.fy)} ({filing.period_label})"


def filing_to_dict(filing):
    return {
        "id": str(filing.id), "form_code": filing.form_code, "fy": filing.fy,
        "period_label": filing.period_label, "period_start": iso(filing.period_start),
        "period_end": iso(filing.period_end), "due_date": iso(filing.due_date), "status": filing.status,
        "filing_path": filing.filing_path, "filed_at": iso(filing.filed_at),
        "acknowledgement_no": filing.acknowledgement_no,
    }


# --- Periods and due dates ---


def financial_year_start(day):
    """1 April of the financial year of `day` (a financial year runs April to March)."""
    return date(day.year if day.month >= 4 else day.year - 1, 4, 1)


def fy_label(fy_start):
    """e.g. "2026-27" for the year that starts on 1 April 2026."""
    return f"{fy_start.year}-{str(fy_start.year + 1)[2:]}"


def periods_of_year(frequency, fy_start):
    """The periods of one financial year as (label, start, end, quarter number)."""
    fy = fy_label(fy_start)
    if frequency == "yearly":
        return [(f"FY {fy}", fy_start, date(fy_start.year + 1, 3, 31), None)]
    months = 1 if frequency == "monthly" else 3
    periods = []
    year, month = fy_start.year, 4
    for number in range(1, 12 // months + 1):
        start = date(year, month, 1)
        end_month = month + months - 1
        end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        label = start.strftime("%b %Y") if frequency == "monthly" else f"Q{number} {fy}"
        periods.append((label, start, end, number if frequency == "quarterly" else None))
        month += months
        if month > 12:  # after December comes January of the next year
            month, year = month - 12, year + 1
    return periods


def due_date(template, period_end, quarter=None, audit=False, itr_form=None):
    """When the filing of the period ending on `period_end` is due, from the template's rule:
    monthly {"day": 11} = the 11th of the next month; quarterly {"quarters": [[7, 13], ...]}
    = [month, day] for Q1..Q4; yearly {"month": 7, "day": 31}, with "audit_month"/"audit_day"
    for a business with an audit and "by_itr_form" {"itr_5": [7, 31]} for one ITR form."""
    rule = template.due_date_rule
    if template.frequency == "monthly":
        month, day = period_end.month % 12 + 1, rule["day"]
    elif template.frequency == "quarterly":
        month, day = rule["quarters"][quarter - 1]
    elif audit and "audit_month" in rule:
        month, day = rule["audit_month"], rule["audit_day"]
    elif itr_form in rule.get("by_itr_form", {}):
        month, day = rule["by_itr_form"][itr_form]
    else:
        month, day = rule["month"], rule["day"]
    due = date(period_end.year, month, day)
    if due <= period_end:  # the first such date after the period
        due = date(period_end.year + 1, month, day)
    return due


def open_filing_ids(filing_ids):
    """The filings among `filing_ids` that are in a requested or active engagement."""
    rows = (db.session.query(EngagementItem.compliance_item_id)
            .join(Engagement, EngagementItem.engagement_id == Engagement.id)
            .filter(EngagementItem.compliance_item_id.in_(filing_ids),
                    Engagement.status.in_(["requested", "active"])))
    return {row[0] for row in rows}


def sync_filings(business_id, profile, today):
    """Make the business's filings of this financial year match its profile; returns
    {"added", "removed", "kept_with_ca"}. New periods whose date has passed start "overdue".
    A filing that no longer applies is deleted unless it is filed or with a CA. A filing not
    started yet gets the current period and due date."""
    fy_start = financial_year_start(today)
    fy = fy_label(fy_start)
    audit = profile.audit_applicable or profile.other_audit_applicable

    wanted = {}  # (form, period start) -> (template, label, start, end, due date)
    for template in ObligationTemplate.query.all():
        if template.effective_from > today or (template.effective_to and template.effective_to <= today):
            continue
        applies = True
        for field, allowed in template.applicability.items():  # e.g. {"gst_scheme": ["composition"]}
            if getattr(profile, field) not in allowed:
                applies = False
        if applies:
            for label, start, end, quarter in periods_of_year(template.frequency, fy_start):
                due = due_date(template, end, quarter, audit, profile.itr_form)
                wanted[(template.form_code, start)] = (template, label, start, end, due)

    existing = {}
    for filing in ComplianceItem.query.filter_by(business_id=business_id, fy=fy):
        existing[(filing.form_code, filing.period_start)] = filing
    in_engagement = open_filing_ids([filing.id for filing in existing.values()])

    counts = {"added": 0, "removed": 0, "kept_with_ca": 0}
    for key, (template, label, start, end, due) in wanted.items():
        status = "overdue" if due < today else "upcoming"
        filing = existing.get(key)
        if filing is None:
            db.session.add(ComplianceItem(business_id=business_id, template_id=template.id,
                                          form_code=template.form_code, fy=fy, period_label=label,
                                          period_start=start, period_end=end, due_date=due, status=status))
            counts["added"] += 1
        else:
            filing.template_id = template.id
            if filing.status in ("upcoming", "overdue") and (filing.period_end, filing.due_date) != (end, due):
                filing.period_label, filing.period_end, filing.due_date, filing.status = label, end, due, status

    for key, filing in existing.items():
        if key in wanted or filing.status in DONE:
            continue
        if filing.status == "with_ca" or filing.id in in_engagement:
            counts["kept_with_ca"] += 1
            continue
        for table in (ChecklistTick, ComplianceItemDocument, ReminderLog, DocumentRequest, EngagementItem):
            table.query.filter_by(compliance_item_id=filing.id).delete()
        db.session.delete(filing)
        counts["removed"] += 1
    return counts


# --- The forms' checklists and texts (content/forms/<FORM>/) ---


def checklist(form_code):
    """The documents to have ready: [{key, label, required, help}]."""
    path = REPO / "content/forms" / FORM_FOLDERS[form_code] / "checklist.yaml"
    entries = []
    for item in yaml.safe_load(path.read_text()).get("items") or []:
        entries.append({"key": item["key"], "label": item["label"],
                        "required": bool(item.get("required")), "help": item.get("help")})
    return entries


def form_content(form_code):
    """The form's explanation and instructions (Markdown) and how finished they are."""
    result = {"form_code": form_code, "status": "DONE", "checklist": checklist(form_code)}
    for page in ("explanation", "instructions"):
        text = (REPO / "content/forms" / FORM_FOLDERS[form_code] / f"{page}.md").read_text()
        status = "TODO"
        if text.startswith("---"):  # a small front matter block with the page's status
            _, front, text = text.split("---", 2)
            status = (yaml.safe_load(front) or {}).get("status", "TODO")
        result[page] = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()  # drop writers' notes
        if status == "TODO" or (status == "DRAFT" and result["status"] == "DONE"):
            result["status"] = status
    return result


def checklist_with_ticks(filing):
    ticked = [tick.checklist_key for tick in ChecklistTick.query.filter_by(compliance_item_id=filing.id)]
    return [{**entry, "ticked": entry["key"] in ticked} for entry in checklist(filing.form_code)]


def missing_documents(filing):
    """The labels of the required documents not ticked yet."""
    return [e["label"] for e in checklist_with_ticks(filing) if e["required"] and not e["ticked"]]


def refresh_status(filing):
    """A filing not started yet: overdue after its due date, else from its checklist."""
    if filing.status not in NOT_STARTED:
        return
    if filing.due_date < today_in_india():
        filing.status = "overdue"
    elif not any(entry["ticked"] for entry in checklist_with_ticks(filing)):
        filing.status = "upcoming"
    elif missing_documents(filing):
        filing.status = "docs_pending"
    else:
        filing.status = "ready"


def set_tick(filing, key, ticked):
    """Tick or untick a checklist entry (the key must be in the checklist)."""
    tick = ChecklistTick.query.filter_by(compliance_item_id=filing.id, checklist_key=key).first()
    if ticked and tick is None:
        db.session.add(ChecklistTick(compliance_item_id=filing.id, checklist_key=key))
    if not ticked and tick is not None:
        db.session.delete(tick)
    db.session.flush()
    refresh_status(filing)


def filing_page(filing):
    """Everything the filing page shows."""
    content = form_content(filing.form_code)
    acknowledgement = None
    if filing.acknowledgement_document_id:
        document = db.session.get(Document, filing.acknowledgement_document_id)
        acknowledgement = {"filename": document.original_filename, "uploaded_at": iso(document.created_at),
                           "verification": verify_acknowledgement(document, filing)}
    if filing.form_code in RENAMED_FORMS and filing.fy >= RENAMED_FORMS[filing.form_code][0]:
        name = RENAMED_FORMS[filing.form_code][2]
    else:
        name = db.session.get(ObligationTemplate, filing.template_id).name
    return {"filing": filing_to_dict(filing), "form_name": name, "content_status": content["status"],
            "explanation": content["explanation"], "instructions": content["instructions"],
            "checklist": checklist_with_ticks(filing), "acknowledgement": acknowledgement}


def record_filed(filing, owner_id, uploader, path):
    """Mark a filing filed with the form's acknowledgement number and file (both optional).
    A file that proves the filing makes it "filed_verified". Returns an error answer or None."""
    number = request.form.get("acknowledgement_no", "").strip().upper()
    if len(number) > 50:
        return error(422, "VALIDATION_ERROR", "The acknowledgement number is too long.")
    if "file" in request.files:
        upload, data, problem = read_upload()
        if problem:
            return problem
        document = save_document(owner_id, uploader.id, "acknowledgement", upload, data)
        document.fy, document.period_label = filing.fy, filing.period_label
        filing.acknowledgement_document_id = document.id
    filing.status, filing.filing_path, filing.filed_at = "filed", path, now()
    filing.acknowledgement_no = number or None
    if filing.acknowledgement_document_id:
        result = verify_acknowledgement(db.session.get(Document, filing.acknowledgement_document_id), filing)
        if result["verified"]:
            filing.status, filing.verified_at = "filed_verified", now()
            filing.acknowledgement_no = filing.acknowledgement_no or result["acknowledgement_no"]
    return None


# --- Does an uploaded acknowledgement prove the filing? ---


def period_shown(fields, filing):
    """A month: its name with the financial year, or "092026". A quarter: the financial year with
    "Q2" or one of its months. A year: the financial year (an ITR may show the assessment year)."""
    years = fields.get("financial_years", [])
    months = []  # (year, month) of every month of the period
    year, month = filing.period_start.year, filing.period_start.month
    while (year, month) <= (filing.period_end.year, filing.period_end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) == 12:
        start = int(filing.fy[:4])
        assessment_year = f"{start + 1}-{str(start + 2)[2:]}"
        return filing.fy in years or (filing.form_code == "itr" and assessment_year in years)
    for y, m in months:
        if f"{y}-{m:02d}" in fields.get("months_with_year", []):
            return True
    if filing.fy not in years:
        return False
    named_month = any(m in fields.get("months", []) for y, m in months)
    if len(months) == 1:
        return named_month
    quarter = int(filing.period_label[1]) if filing.period_label.startswith("Q") else None
    return named_month or quarter in fields.get("quarters", [])


def verify_acknowledgement(document, filing):
    """It must name the form, show the period, have an ARN (the one typed, if any) and a date on
    or after the period's end. Returns {verified, problems, acknowledgement_no, filing_date}."""
    fields = document.ocr_fields or {}
    number, filed_on = fields.get("acknowledgement_no"), fields.get("filing_date")
    problems = []
    if document.ocr_status != "processed":
        problems.append(fields.get("error") or "The file has not been read yet.")
    else:
        if filing.form_code not in fields.get("form_codes", []):
            problems.append(f"It does not name the form {form_name(filing.form_code, filing.fy)}.")
        if not period_shown(fields, filing):
            problems.append(f"It does not show the period {filing.period_label}.")
        typed = (filing.acknowledgement_no or "").replace(" ", "").upper()
        if number is None:
            problems.append("No acknowledgement or ARN number was found.")
        elif typed and typed != number:
            problems.append(f"Its number ({number}) is not the one typed ({typed}).")
        if filed_on is None:
            problems.append("No filing date was found.")
        elif date.fromisoformat(filed_on) < filing.period_end:
            problems.append("Its date is before the end of the period.")
    return {"verified": not problems, "problems": problems, "acknowledgement_no": number,
            "filing_date": filed_on}
