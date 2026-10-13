# Admin pages: the numbers on the home page, every account, and checking CAs (verify or reject
# them after looking at their Certificate of Practice). Admins never open other documents.

from flask import jsonify, request

from app import app
from filings import DONE
from helpers import (
    current_user, error, date, iso, page_of, role_required, send_document, send_email, now,
)
from models import Business, CaProfile, ComplianceItem, Document, Engagement, User, db, now
from routes_marketplace import profile_to_dict


def ca_to_dict(profile):
    """Everything an admin sees about a CA (their numbers too, to check them)."""
    return {**profile_to_dict(profile), "user_id": str(profile.user_id), "full_name": profile.user.full_name,
            "email": profile.user.email, "verified_at": iso(profile.verified_at)}


@app.route("/api/v1/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    return jsonify({"message": f"Welcome, {current_user().full_name}"})


@app.route("/api/v1/admin/stats")
@role_required("admin")
def admin_stats():
    """Counts for the home page, and how many filings were late (the overdue rate)."""
    users = {"business": 0, "ca": 0, "admin": 0}
    for user in User.query.all():
        users[user.role] += 1
    cas = {"pending": 0, "verified": 0, "rejected": 0}
    for profile in CaProfile.query.all():
        cas[profile.verification_status] += 1
    statuses = {s: 0 for s in ("upcoming", "docs_pending", "ready", "with_ca", "filed", "filed_verified", "overdue")}
    due = late = 0
    for filing in ComplianceItem.query.all():
        statuses[filing.status] += 1
        if filing.due_date < now():
            due += 1
            filed_on_time = filing.status in DONE and filing.filed_at and date(filing.filed_at) <= filing.due_date
            if not filed_on_time:
                late += 1
    open_engagements = Engagement.query.filter(Engagement.status.in_(["requested", "active"])).count()
    return jsonify({"users_by_role": users, "businesses": Business.query.count(), "cas_by_status": cas,
                    "open_engagements": open_engagements, "filings_by_status": statuses,
                    "filings_due_so_far": due, "filings_late": late,
                    "overdue_rate": round(late * 100 / due, 1) if due else None})


@app.route("/api/v1/admin/users")
@role_required("admin")
def admin_users():
    """Every account, newest first; ?role= and ?search= (name or email) are optional."""
    query = User.query.order_by(User.created_at.desc())
    if request.args.get("role"):
        query = query.filter_by(role=request.args["role"])
    search = request.args.get("search", "").strip()
    if search:
        query = query.filter(User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    return jsonify(page_of(query, lambda user: {
        "id": str(user.id), "full_name": user.full_name, "email": user.email, "role": user.role,
        "email_verified": user.email_verified, "created_at": iso(user.created_at)}))


@app.route("/api/v1/admin/cas")
@role_required("admin")
def admin_cas():
    """CA profiles (?status=pending, verified or rejected), the longest waiting first."""
    query = CaProfile.query.order_by(CaProfile.updated_at)
    if request.args.get("status"):
        query = query.filter_by(verification_status=request.args["status"])
    return jsonify([ca_to_dict(profile) for profile in query])


@app.route("/api/v1/admin/cas/<uuid:ca_id>")
@role_required("admin")
def admin_ca(ca_id):
    profile = db.session.get(CaProfile, ca_id)
    if profile is None:
        return error(404, "CA_NOT_FOUND", "This CA was not found.")
    return jsonify(ca_to_dict(profile))


@app.route("/api/v1/admin/cas/<uuid:ca_id>/certificate")
@role_required("admin")
def admin_ca_certificate(ca_id):
    profile = db.session.get(CaProfile, ca_id)
    if profile is None:
        return error(404, "CA_NOT_FOUND", "This CA was not found.")
    if profile.cop_document_id is None:
        return error(404, "CERTIFICATE_MISSING", "This CA has not uploaded a certificate.")
    return send_document(db.session.get(Document, profile.cop_document_id))


@app.route("/api/v1/admin/cas/<uuid:ca_id>/verify", methods=["POST"])
@role_required("admin")
def verify_ca(ca_id):
    """Verify a CA (they must have uploaded their certificate); the CA is emailed."""
    profile = db.session.get(CaProfile, ca_id)
    if profile is None:
        return error(404, "CA_NOT_FOUND", "This CA was not found.")
    if profile.cop_document_id is None:
        return error(409, "CERTIFICATE_MISSING", "Ask the CA to upload their certificate first.")
    profile.verification_status, profile.rejection_reason = "verified", None
    profile.verified_at, profile.verified_by_id = now(), current_user().id
    db.session.commit()
    if profile.user.email_notifications:
        send_email(profile.user.email, "Your CA Helper profile is verified", "ca_verified", name=profile.user.full_name)
    return jsonify(ca_to_dict(profile))


@app.route("/api/v1/admin/cas/<uuid:ca_id>/reject", methods=["POST"])
@role_required("admin")
def reject_ca(ca_id):
    """Reject a CA with a reason they see on their profile page and in an email."""
    profile = db.session.get(CaProfile, ca_id)
    if profile is None:
        return error(404, "CA_NOT_FOUND", "This CA was not found.")
    reason = str((request.get_json(silent=True) or {}).get("reason") or "").strip()
    if not reason or len(reason) > 500:
        return error(422, "VALIDATION_ERROR", "Give a reason (up to 500 characters).")
    profile.verification_status, profile.rejection_reason = "rejected", reason
    profile.verified_at = profile.verified_by_id = None
    db.session.commit()
    if profile.user.email_notifications:
        send_email(profile.user.email, "Your CA Helper profile needs a correction", "ca_rejected",
                   name=profile.user.full_name, reason=reason)
    return jsonify(ca_to_dict(profile))
