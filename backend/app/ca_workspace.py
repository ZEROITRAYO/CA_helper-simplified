"""The CA's workspace: their clients sorted by urgency, one client's page, document
requests, marking a filing as filed, and batches of the same filing across clients.

A CA works only on the filings of their ACTIVE engagements. Every route that names a
business checks that first (client_work), and the code keeps to the active work, so a
CA with two clients, or a business with two CAs, never mixes them up.

Urgency is a simple weighted sum, each part with its reason, so the CA sees why a client
is flagged. The weights are the constants below.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app import alerts, compliance, documents, marketplace, onboarding
from app.models import (
    Business, ComplianceStatus, DocumentRequest, DocumentRequestStatus, Engagement, EngagementStatus,
    FilingPath,
    NotificationType, User, UserRole, db, today_in_india, utcnow,
)
from app.utils import (
    ApiError, current_business, current_user, iso, json_body, read_id, read_text, roles_required,
)

bp = Blueprint("ca_workspace", __name__)

# Urgency weights (product weights, not legal values).
POINTS_PER_OVERDUE_FILING = 40
POINTS_DUE_WITHIN_3_DAYS = 25  # the next deadline is 0 to 3 days away
POINTS_DUE_WITHIN_7_DAYS = 10  # 4 to 7 days away
POINTS_PER_MISSING_DOCUMENT = 5  # a required checklist entry not ticked
POINTS_PER_OPEN_REQUEST = 3  # a document asked for and not received yet


def request_to_dict(document_request):
    """One document request."""
    filing = document_request.filing
    return {
        "id": str(document_request.id), "compliance_item_id": str(filing.id),
        "form_code": filing.form_code, "period_label": filing.period_label,
        "checklist_key": document_request.checklist_key, "message": document_request.message,
        "status": document_request.status, "created_at": iso(document_request.created_at),
        "fulfilled_at": iso(document_request.fulfilled_at),
        "document_id": str(document_request.document_id) if document_request.document_id else None,
    }


def work_by_client():
    """{business id: {filing: engagement}} for the logged-in CA's ACTIVE engagements.
    404 CA_PROFILE_NOT_FOUND before the profile is saved."""
    profile = marketplace.own_profile(current_user())
    clients = {}
    for engagement, item in marketplace.active_items(profile.id):
        clients.setdefault(engagement.business_id, {})[item.filing] = engagement
    return clients


def client_work(business_id):
    """{filing: engagement} of one client. 404 BUSINESS_NOT_FOUND unless the CA has an
    active engagement with it."""
    work = work_by_client().get(business_id)
    if work is None:
        raise ApiError(404, "BUSINESS_NOT_FOUND", "This business was not found.")
    return work


def open_requests(engagements, filings):
    """The open document requests of these engagements for these filings, oldest first."""
    return db.session.scalars(select(DocumentRequest).where(
        DocumentRequest.engagement_id.in_([e.id for e in engagements]),
        DocumentRequest.compliance_item_id.in_([f.id for f in filings]),
        DocumentRequest.status == DocumentRequestStatus.OPEN,
    ).order_by(DocumentRequest.created_at)).all()


def _urgency(filings, open_request_count, today):
    """The urgency score, its reasons and the counts of one client's open filings."""
    overdue = [filing for filing in filings if filing.due_date < today]
    upcoming = sorted(filing.due_date for filing in filings if filing.due_date >= today)
    missing = sum(len(compliance.missing_documents(filing)) for filing in filings)
    reasons = []
    if overdue:
        reasons.append({"reason": f"{len(overdue)} filing(s) overdue",
                        "points": len(overdue) * POINTS_PER_OVERDUE_FILING})
    days = (upcoming[0] - today).days if upcoming else None
    if days is not None and days <= 3:
        reasons.append({"reason": f"Next deadline in {days} day(s)", "points": POINTS_DUE_WITHIN_3_DAYS})
    elif days is not None and days <= 7:
        reasons.append({"reason": f"Next deadline in {days} days", "points": POINTS_DUE_WITHIN_7_DAYS})
    if missing:
        reasons.append({"reason": f"{missing} required document(s) not ready",
                        "points": missing * POINTS_PER_MISSING_DOCUMENT})
    if open_request_count:
        reasons.append({"reason": f"{open_request_count} document request(s) not answered",
                        "points": open_request_count * POINTS_PER_OPEN_REQUEST})
    return {
        "score": sum(reason["points"] for reason in reasons), "reasons": reasons,
        "next_deadline": upcoming[0] if upcoming else None, "overdue_count": len(overdue),
        "missing_documents": missing,
    }


# --- Routes for the CA -------------------------------------------------------------------


@bp.get("/ca-workspace/dashboard")
@roles_required(UserRole.CA)
def dashboard():
    return jsonify({"message": f"Welcome, {current_user().full_name}"})


@bp.get("/ca-workspace/clients")
@roles_required(UserRole.CA)
def list_clients():
    """The CA's clients (ACTIVE engagements), most urgent first."""
    rows = []
    for business_id, work in work_by_client().items():
        not_filed = [f for f in work if f.status not in compliance.DONE_STATUSES]
        requests = open_requests(work.values(), work)
        urgency = _urgency(not_filed, len(requests), today_in_india())
        rows.append({
            "business_id": str(business_id),
            "business_name": db.session.get(Business, business_id).legal_name,
            "filing_count": len(work), "open_filing_count": len(not_filed),
            "open_request_count": len(requests), **urgency,
            "next_deadline": iso(urgency["next_deadline"]),
        })
    rows.sort(key=lambda row: (-row["score"], row["business_name"]))
    return jsonify(rows)


@bp.get("/ca-workspace/clients/<uuid:business_id>")
@roles_required(UserRole.CA)
def get_client(business_id):
    """One client: the business, its profile and the CA's engaged filings with documents."""
    work = client_work(business_id)
    filings = sorted(work, key=lambda filing: filing.due_date)
    files_by_filing = documents.documents_by_filing(filings)
    requests = open_requests(work.values(), filings)
    page = onboarding.business_page(db.session.get(Business, business_id))
    page["filings"] = [
        {
            "filing": compliance.filing_to_dict(filing),
            "checklist": compliance.checklist_with_ticks(filing),
            "documents": files_by_filing[filing.id],
            "open_requests": [request_to_dict(r) for r in requests if r.compliance_item_id == filing.id],
        }
        for filing in filings
    ]
    return jsonify(page)


def engaged_filing(work, item_id):
    """(filing, engagement) of one filing in the CA's active work. 404 FILING_NOT_FOUND."""
    for filing, engagement in work.items():
        if filing.id == item_id:
            return filing, engagement
    raise ApiError(404, "FILING_NOT_FOUND", "This filing is not in your active work.")


@bp.post("/ca-workspace/clients/<uuid:business_id>/document-requests")
@roles_required(UserRole.CA)
def create_document_request(business_id):
    """Ask the client for a document for an engaged filing; the owner is told."""
    data = json_body()
    item_id = read_id(data, "compliance_item_id")
    checklist_key = read_text(data, "checklist_key", 50, required=False) or documents.GENERAL_KEY
    message = read_text(data, "message", 1000)
    filing, engagement = engaged_filing(client_work(business_id), item_id)
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already filed.")
    documents.check_key(filing, checklist_key)
    document_request = DocumentRequest(engagement_id=engagement.id, compliance_item_id=item_id,
                                       checklist_key=checklist_key, message=message)
    db.session.add(document_request)
    user, business = current_user(), engagement.business
    owner = db.session.get(User, business.user_id)
    # Say who wrote to whom, so the email cannot be read the wrong way round.
    title = f"{user.full_name} asked you for a document for {compliance.filing_name(filing)}"
    body = (
        f"From: {user.full_name} (your CA)\nTo: {business.legal_name}\n\n"
        f"Message: {message}\n\nUpload the document from the filing's page."
    )
    alerts.notify(owner, NotificationType.DOCUMENT_REQUEST, title, body, f"/business/compliance/{filing.id}")
    db.session.commit()
    alerts.email_notice(owner, title, body)
    return jsonify(request_to_dict(document_request)), 201


@bp.post("/ca-workspace/clients/<uuid:business_id>/filings/<uuid:item_id>/mark-filed")
@roles_required(UserRole.CA)
def mark_filed(business_id, item_id):
    """The CA filed an engaged filing (path "ca"); the engagement completes after its last
    filing. 409 ALREADY_FILED or FILING_NOT_WITH_CA."""
    compliance.read_acknowledgement_no()  # checked before anything else
    filing, engagement = engaged_filing(client_work(business_id), item_id)
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(409, "ALREADY_FILED", "This filing is already marked as filed.")
    if filing.status != ComplianceStatus.WITH_CA:
        raise ApiError(409, "FILING_NOT_WITH_CA", "This filing is not with you.")
    user, business = current_user(), engagement.business
    compliance.record_filed(filing, business.user_id, user, FilingPath.CA)
    # Requests for a filed filing can no longer be answered.
    for document_request in open_requests([engagement], [filing]):
        document_request.status = DocumentRequestStatus.CANCELLED
    owner = db.session.get(User, business.user_id)
    title = f"Your CA filed {compliance.filing_name(filing)}"
    body = f"{user.full_name} marked it as filed"
    body += f" (acknowledgement number {filing.acknowledgement_no})." if filing.acknowledgement_no else "."
    alerts.notify(owner, NotificationType.ENGAGEMENT_UPDATE, title, body, f"/business/compliance/{filing.id}")
    completed = marketplace.complete_if_all_filed(engagement)
    db.session.commit()
    alerts.email_notice(owner, title, body)
    return jsonify({"compliance_item_id": str(filing.id), "status": filing.status,
                    "acknowledgement_no": filing.acknowledgement_no, "engagement_completed": completed})


@bp.get("/ca-workspace/batches")
@roles_required(UserRole.CA)
def list_batches():
    """The CA's open filings across clients, grouped by form and due date."""
    groups = {}
    for business_id, work in work_by_client().items():
        business = db.session.get(Business, business_id)
        for filing in work:
            if filing.status in compliance.DONE_STATUSES:
                continue
            checklist = compliance.checklist_with_ticks(filing)
            missing = compliance.missing_documents(filing)
            required_total = sum(1 for entry in checklist if entry["required"])
            groups.setdefault((filing.due_date, filing.form_code), []).append({
                "business_id": str(business_id), "business_name": business.legal_name,
                "compliance_item_id": str(filing.id), "period_label": filing.period_label,
                "status": filing.status, "required_total": required_total,
                "required_ready": required_total - len(missing), "missing": missing,
                "ready": len(missing) == 0,
            })
    batches = []
    for (due_date, form_code), filings in sorted(groups.items()):
        filings.sort(key=lambda row: row["business_name"])
        batches.append({"form_code": form_code, "due_date": iso(due_date),
                        "ready_count": sum(1 for row in filings if row["ready"]), "filings": filings})
    return jsonify(batches)


@bp.post("/ca-workspace/document-requests/<uuid:request_id>/cancel")
@roles_required(UserRole.CA)
def cancel_document_request(request_id):
    """The CA takes an open request back (only for their active work)."""
    document_request = db.session.get(DocumentRequest, request_id)
    engagement_ids = {e.id for work in work_by_client().values() for e in work.values()}
    if document_request is None or document_request.engagement_id not in engagement_ids:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if document_request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    document_request.status = DocumentRequestStatus.CANCELLED
    db.session.commit()
    return jsonify(request_to_dict(document_request))


# --- Routes for the business -------------------------------------------------------------


def business_requests(business):
    """The business's open document requests to its CAs of ACTIVE engagements, oldest first."""
    return db.session.scalars(
        select(DocumentRequest).join(Engagement).where(
            Engagement.business_id == business.id, Engagement.status == EngagementStatus.ACTIVE,
            DocumentRequest.status == DocumentRequestStatus.OPEN,
        ).order_by(DocumentRequest.created_at)
    ).all()


@bp.get("/ca-workspace/document-requests")
@roles_required(UserRole.BUSINESS)
def list_business_requests():
    """The business's open document requests (its to-dos), oldest first."""
    item_id = None
    if "compliance_item_id" in request.args:
        item_id = read_id(request.args, "compliance_item_id", location="query")
    rows = []
    for document_request in business_requests(current_business()):
        if item_id is None or document_request.compliance_item_id == item_id:
            rows.append({**request_to_dict(document_request),
                         "ca_name": document_request.engagement.ca.user.full_name})
    return jsonify(rows)


@bp.post("/ca-workspace/document-requests/<uuid:request_id>/fulfil")
@roles_required(UserRole.BUSINESS)
def fulfil_document_request(request_id):
    """Answer a request with a document: it is linked and ticked; the CA is told."""
    document_id = read_id(json_body(), "document_id")
    business = current_business()
    document_request = db.session.get(DocumentRequest, request_id)
    engagement = document_request.engagement if document_request else None
    mine = engagement and engagement.business_id == business.id
    if not mine or engagement.status != EngagementStatus.ACTIVE:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if document_request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    document = documents.attach_document(business, current_user(), document_id,
                                         document_request.compliance_item_id, document_request.checklist_key)
    document_request.status = DocumentRequestStatus.FULFILLED
    document_request.fulfilled_at = utcnow()
    document_request.document_id = document_id
    ca_user = engagement.ca.user
    title = f"{business.legal_name} sent you the document you asked for"
    body = (
        f"From: {business.legal_name} (your client)\nTo: {ca_user.full_name}\n\n"
        f"Filing: {compliance.filing_name(document_request.filing)}\n"
        f"Your request: {document_request.message}\n"
        f"Document sent: {document.original_filename}"
    )
    alerts.notify(ca_user, NotificationType.DOCUMENT_REQUEST, title, body, f"/ca/clients/{business.id}")
    db.session.commit()
    alerts.email_notice(ca_user, title, body)
    return jsonify(request_to_dict(document_request))
