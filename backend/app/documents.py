"""The document vault: uploaded files (stored encrypted in `documents.content`), their
links to filings, and reading them locally (OCR) to check acknowledgements.

A document is linked to a filing per checklist key (`compliance_item_documents`), or with
the key "general" when it answers no checklist entry; one file can serve several filings.
Linking a file to a checklist entry also ticks that entry. Once a filing is filed, its
links are fixed: they are the proof of what was filed. Admins never open documents.
"""

import hashlib
import io
import logging
from datetime import date

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import delete, or_, select, update

from app import compliance, marketplace, ocr
from app.models import (
    ComplianceItem, ComplianceItemDocument, Document, DocumentRequest, DocumentType, OcrStatus,
    UserRole, db, decrypt_bytes, encrypt_bytes, today_in_india,
)
from app.utils import (
    ApiError, current_business, current_user, invalid, iso, json_body, page_of, read_choice,
    read_id, read_text, read_upload, roles_required,
)

log = logging.getLogger(__name__)

bp = Blueprint("documents", __name__)

# The checklist key of a link that answers no checklist entry.
GENERAL_KEY = "general"


def add_document(owner_id, uploaded_by_id, doc_type):
    """Store the request's uploaded file and add its row (file check errors pass through).
    The file is read locally (OCR) and only non-personal facts are kept; that never fails."""
    upload, data = read_upload()
    document = Document(
        owner_id=owner_id, uploaded_by_id=uploaded_by_id, doc_type=doc_type,
        original_filename=(upload.filename or "upload")[:255], content=encrypt_bytes(data),
        mime_type=upload.mimetype, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
    )
    db.session.add(document)
    db.session.flush()  # gives document.id
    try:
        text = ocr.extract_text(data, document.mime_type)
        document.ocr_fields = ocr.read_proof_fields(text, today_in_india())
        document.ocr_status = OcrStatus.PROCESSED
    except ocr.OcrError as error:
        document.ocr_status, document.ocr_fields = OcrStatus.FAILED, {"error": str(error)}
    except Exception:  # an unexpected library error must not lose the upload
        log.exception("OCR failed for document %s", document.id)
        document.ocr_status = OcrStatus.FAILED
        document.ocr_fields = {"error": "The file could not be read."}
    return document


def period_shown(fields, filing):
    """Does the acknowledgement show the filing's period?

    A month: "September" with the financial year, or "092026". A quarter: the financial
    year with "Q2" or one of its months. A year: the financial year; an ITR may show the
    assessment year instead (the year after, "2027-28" for FY 2026-27).
    """
    years = fields.get("financial_years", [])
    fy_start = int(filing.fy[:4])
    # (year, month) of every month of the filing's period, e.g. Jul, Aug, Sep 2026.
    months = []
    year, month = filing.period_start.year, filing.period_start.month
    while (year, month) <= (filing.period_end.year, filing.period_end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) == 12:  # a whole financial year
        return filing.fy in years or (
            filing.form_code == "itr" and f"{fy_start + 1}-{str(fy_start + 2)[2:]}" in years
        )
    if any(f"{y}-{m:02d}" in fields.get("months_with_year", []) for y, m in months):
        return True
    if filing.fy not in years:
        return False
    named_month = any(m in fields.get("months", []) for _, m in months)
    if len(months) == 1:
        return named_month
    quarter = int(filing.period_label[1]) if filing.period_label.startswith("Q") else None
    return quarter in fields.get("quarters", []) or named_month


def verify_acknowledgement(document, filing):
    """Does this acknowledgement prove this filing?

    It must name the form, show the period, have an acknowledgement / ARN number (the
    same as the one typed, if any) and a filing date on or after the period's end.
    Returns {verified, problems (what did not match, for the page), acknowledgement_no,
    filing_date}.
    """
    fields = document.ocr_fields or {}
    number, filing_date = fields.get("acknowledgement_no"), fields.get("filing_date")
    if document.ocr_status != OcrStatus.PROCESSED:
        problems = [fields.get("error") or "The file has not been read yet."]
    else:
        problems = []
        if filing.form_code not in fields.get("form_codes", []):
            problems.append(f"It does not name the form {compliance.form_name(filing.form_code, filing.fy)}.")
        if not period_shown(fields, filing):
            problems.append(f"It does not show the period {filing.period_label}.")
        typed = (filing.acknowledgement_no or "").replace(" ", "").upper()
        if number is None:
            problems.append("No acknowledgement or ARN number was found.")
        elif typed and typed != number:
            problems.append(f"Its number ({number}) is not the one typed ({typed}).")
        if filing_date is None:
            problems.append("No filing date was found.")
        elif date.fromisoformat(filing_date) < filing.period_end:
            problems.append("Its date is before the end of the period.")
    return {"verified": not problems, "problems": problems, "acknowledgement_no": number,
            "filing_date": filing_date}


def get_document(document_id, owner_id=None):
    """A document (of `owner_id`, when given). 404 DOCUMENT_NOT_FOUND."""
    document = db.session.get(Document, document_id) if document_id else None
    if document is None or (owner_id is not None and document.owner_id != owner_id):
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document


def send_document(document):
    """The decrypted file as a download."""
    data = io.BytesIO(decrypt_bytes(document.content))
    return send_file(data, mimetype=document.mime_type, download_name=document.original_filename)


def remove_document(document_id):
    """Delete a document's links and row (callers clear what points to it first)."""
    document = db.session.get(Document, document_id)
    if document is None:
        return
    links = delete(ComplianceItemDocument).where(ComplianceItemDocument.document_id == document.id)
    db.session.execute(links)
    db.session.execute(
        update(DocumentRequest).where(DocumentRequest.document_id == document.id).values(document_id=None)
    )
    db.session.delete(document)


def open_filing(business, item_id):
    """A filing of this business. 404 FILING_NOT_FOUND; 409 FILING_LOCKED once filed."""
    filing = compliance.own_filing(business, item_id)
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is filed, so its documents can no longer change.")
    return filing


def check_key(filing, checklist_key):
    """422 UNKNOWN_CHECKLIST_KEY unless the key is "general" or in the form's checklist."""
    keys = [entry["key"] for entry in compliance.checklist(filing.form_code)]
    if checklist_key != GENERAL_KEY and checklist_key not in keys:
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")


def link(filing, document, checklist_key, user):
    """Link the document to the filing (once) and tick the checklist entry."""
    existing = db.session.scalar(select(ComplianceItemDocument).where(
        ComplianceItemDocument.compliance_item_id == filing.id,
        ComplianceItemDocument.document_id == document.id,
        ComplianceItemDocument.checklist_key == checklist_key,
    ))
    if existing is None:
        db.session.add(ComplianceItemDocument(compliance_item_id=filing.id, document_id=document.id,
                                              checklist_key=checklist_key, linked_by_id=user.id))
    if checklist_key != GENERAL_KEY:
        compliance.set_tick(filing, checklist_key, True)


def attach_document(business, user, document_id, item_id, checklist_key):
    """Link one of the business's documents to one of its open filings (no commit)."""
    document = get_document(document_id, business.user_id)
    filing = open_filing(business, item_id)
    check_key(filing, checklist_key)
    link(filing, document, checklist_key, user)
    return document


def document_to_dict(document):
    """A document's fields plus its `links` to filings."""
    links = []
    for row, filing in db.session.execute(
        select(ComplianceItemDocument, ComplianceItem).join(ComplianceItem)
        .where(ComplianceItemDocument.document_id == document.id)
    ):
        links.append({"id": str(row.id), "compliance_item_id": str(filing.id),
                      "form_code": filing.form_code, "period_label": filing.period_label,
                      "checklist_key": row.checklist_key})
    guess = (document.ocr_fields or {}).get("type_guess")
    return {
        "id": str(document.id), "doc_type": document.doc_type,
        "original_filename": document.original_filename, "mime_type": document.mime_type,
        "size_bytes": document.size_bytes, "fy": document.fy, "period_label": document.period_label,
        "ocr_status": document.ocr_status, "created_at": iso(document.created_at), "links": links,
        # The type the file seems to be when that is not the type chosen at upload (also "Other").
        "type_warning": guess if guess and guess != document.doc_type else None,
    }


def documents_by_filing(filings):
    """{filing id: [files]}: the linked files and the acknowledgement of each."""
    result = {filing.id: [] for filing in filings}
    rows = list(db.session.execute(
        select(ComplianceItemDocument.compliance_item_id, ComplianceItemDocument.checklist_key, Document)
        .join(Document).where(ComplianceItemDocument.compliance_item_id.in_(list(result)))
        .order_by(Document.created_at)
    ))
    for filing in filings:
        if filing.acknowledgement_document_id is not None:
            acknowledgement = db.session.get(Document, filing.acknowledgement_document_id)
            rows.append((filing.id, "acknowledgement", acknowledgement))
    for filing_id, checklist_key, document in rows:
        result[filing_id].append({
            "document_id": str(document.id), "original_filename": document.original_filename,
            "doc_type": document.doc_type, "size_bytes": document.size_bytes,
            "created_at": iso(document.created_at), "checklist_key": checklist_key,
        })
    return result


# --- Routes ------------------------------------------------------------------------------


@bp.post("/documents")
@roles_required(UserRole.BUSINESS)
def upload_document():
    """Upload a file to the vault; optionally link it to a filing."""
    form = request.form
    doc_type = read_choice(form, "doc_type", DocumentType, location="form")
    if doc_type == DocumentType.CERTIFICATE_OF_PRACTICE:
        raise invalid("doc_type", "This type cannot be uploaded here.", "form")
    item_id = read_id(form, "compliance_item_id", required=False, location="form")
    checklist_key = read_text(form, "checklist_key", 50, required=False, location="form") or GENERAL_KEY
    business, user = current_business(), current_user()
    filing = None
    if item_id is not None:  # checked before the file is stored
        filing = open_filing(business, item_id)
        check_key(filing, checklist_key)
    document = add_document(business.user_id, user.id, doc_type)
    if filing is not None:
        document.fy, document.period_label = filing.fy, filing.period_label
        link(filing, document, checklist_key, user)
    db.session.commit()
    return jsonify(document_to_dict(document)), 201


@bp.get("/documents")
@roles_required(UserRole.BUSINESS)
def list_documents():
    """The business's documents, newest first, paginated; optionally only one filing's."""
    stmt = select(Document).where(Document.owner_id == current_business().user_id)
    if "compliance_item_id" in request.args:
        item_id = read_id(request.args, "compliance_item_id", location="query")
        filing = db.session.get(ComplianceItem, item_id)
        linked = select(ComplianceItemDocument.document_id).where(
            ComplianceItemDocument.compliance_item_id == item_id
        )
        acknowledgement_id = filing.acknowledgement_document_id if filing else None
        stmt = stmt.where(or_(Document.id.in_(linked), Document.id == acknowledgement_id))
    return jsonify(page_of(stmt.order_by(Document.created_at.desc(), Document.id), document_to_dict))


@bp.get("/documents/<uuid:document_id>/file")
@roles_required(UserRole.BUSINESS, UserRole.CA)
def get_document_file(document_id):
    """The file, for its owner or a CA with active access. 404 for anyone else."""
    user = current_user()
    document = get_document(document_id)
    profile = marketplace.own_profile(user, required=False) if user.role == UserRole.CA else None
    allowed = profile is not None and marketplace.ca_can_open_document(profile.id, document.id)
    if document.owner_id != user.id and not allowed:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return send_document(document)


@bp.delete("/documents/<uuid:document_id>")
@roles_required(UserRole.BUSINESS)
def delete_document(document_id):
    """Delete a document unless it proves a filing (409 DOCUMENT_IN_USE)."""
    document = get_document(document_id, current_business().user_id)
    acknowledged = db.session.scalar(
        select(ComplianceItem).where(ComplianceItem.acknowledgement_document_id == document.id)
    )
    if acknowledged is not None:
        raise ApiError(409, "DOCUMENT_IN_USE",
                       f"This is the acknowledgement of {compliance.filing_name(acknowledged)}. "
                       'Undo "mark as filed" on that filing to remove it.')
    for filing in db.session.scalars(
        select(ComplianceItem).join(ComplianceItemDocument)
        .where(ComplianceItemDocument.document_id == document.id)
    ):
        if filing.status in compliance.DONE_STATUSES:
            raise ApiError(409, "DOCUMENT_IN_USE",
                           f"This document is proof for {compliance.filing_name(filing)}, which is filed, "
                           "so it cannot be deleted.")
    remove_document(document.id)
    db.session.commit()
    return "", 204


@bp.post("/documents/<uuid:document_id>/links")
@roles_required(UserRole.BUSINESS)
def link_document(document_id):
    """Link a document to a filing once; a key other than "general" is ticked."""
    data = json_body()
    item_id = read_id(data, "compliance_item_id")
    checklist_key = read_text(data, "checklist_key", 50, required=False) or GENERAL_KEY
    document = attach_document(current_business(), current_user(), document_id, item_id, checklist_key)
    db.session.commit()
    return jsonify(document_to_dict(document))


@bp.delete("/documents/links/<uuid:link_id>")
@roles_required(UserRole.BUSINESS)
def unlink_document(link_id):
    """Remove one link between a document and a filing (the tick stays)."""
    business = current_business()
    row = db.session.get(ComplianceItemDocument, link_id)
    if row is None or db.session.get(Document, row.document_id).owner_id != business.user_id:
        raise ApiError(404, "LINK_NOT_FOUND", "This link was not found.")
    open_filing(business, row.compliance_item_id)
    db.session.delete(row)
    db.session.commit()
    return "", 204
