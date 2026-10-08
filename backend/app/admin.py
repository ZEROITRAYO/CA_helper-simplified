"""Admin screens: the counts on the home page, every account, and checking CAs (verify or
reject, with the Certificate of Practice). Admins see metadata only, never document
contents other than a CA's certificate."""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app import compliance, documents, marketplace
from app.models import (
    Business, CaProfile, CaVerificationStatus, Engagement, EngagementStatus, User, UserRole, db, utcnow,
)
from app.utils import (
    ApiError, current_user, iso, json_body, page_of, read_choice, read_text, roles_required, send_email,
)

bp = Blueprint("admin", __name__)


def ca_to_dict(profile):
    """Everything an admin sees about a CA (their numbers too, for checking)."""
    return {
        **marketplace.profile_to_dict(profile), "user_id": str(profile.user_id),
        "full_name": profile.user.full_name, "email": profile.user.email,
        "verified_at": iso(profile.verified_at),
    }


def get_profile(ca_id):
    profile = db.session.get(CaProfile, ca_id)
    if profile is None:
        raise ApiError(404, "CA_NOT_FOUND", "This CA was not found.")
    return profile


@bp.get("/admin/dashboard")
@roles_required(UserRole.ADMIN)
def dashboard():
    return jsonify({"message": f"Welcome, {current_user().full_name}"})


@bp.get("/admin/stats")
@roles_required(UserRole.ADMIN)
def get_stats():
    """Counts for the home page: users, businesses, CAs, open engagements and filings."""
    users_by_role = {role.value: 0 for role in UserRole}
    for role in db.session.scalars(select(User.role)):
        users_by_role[role] += 1
    cas_by_status = {status.value: 0 for status in CaVerificationStatus}
    for status in db.session.scalars(select(CaProfile.verification_status)):
        cas_by_status[status] += 1
    open_engagements = select(func.count()).select_from(Engagement).where(
        Engagement.status.in_([EngagementStatus.REQUESTED, EngagementStatus.ACTIVE])
    )
    return jsonify({
        "users_by_role": users_by_role,
        "businesses": db.session.scalar(select(func.count(Business.id))),
        "cas_by_status": cas_by_status,
        "open_engagements": db.session.scalar(open_engagements),
        **compliance.filing_stats(),
    })


@bp.get("/admin/users")
@roles_required(UserRole.ADMIN)
def list_users():
    """Every account, newest first; optional role and ?search= (name or email), paginated."""
    stmt = select(User).order_by(User.created_at.desc())
    role = read_choice(request.args, "role", UserRole, required=False, location="query")
    if role:
        stmt = stmt.where(User.role == role)
    search = request.args.get("search", "").strip()[:100]
    if search:
        stmt = stmt.where(User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    return jsonify(page_of(stmt, lambda user: {
        "id": str(user.id), "full_name": user.full_name, "email": user.email, "role": user.role,
        "email_verified": user.email_verified_at is not None, "created_at": iso(user.created_at),
    }))


@bp.get("/admin/cas")
@roles_required(UserRole.ADMIN)
def list_cas():
    """CA profiles (?status=pending|verified|rejected), the longest-waiting first."""
    stmt = select(CaProfile).order_by(CaProfile.updated_at)
    status = read_choice(request.args, "status", CaVerificationStatus, required=False, location="query")
    if status:
        stmt = stmt.where(CaProfile.verification_status == status)
    return jsonify([ca_to_dict(profile) for profile in db.session.scalars(stmt)])


@bp.get("/admin/cas/<uuid:ca_id>")
@roles_required(UserRole.ADMIN)
def get_ca(ca_id):
    return jsonify(ca_to_dict(get_profile(ca_id)))


@bp.get("/admin/cas/<uuid:ca_id>/certificate")
@roles_required(UserRole.ADMIN)
def get_ca_certificate(ca_id):
    """The CA's Certificate of Practice file, to check it. 404 CERTIFICATE_MISSING."""
    profile = get_profile(ca_id)
    if profile.cop_document_id is None:
        raise ApiError(404, "CERTIFICATE_MISSING", "This CA has not uploaded a certificate.")
    return documents.send_document(documents.get_document(profile.cop_document_id))


@bp.post("/admin/cas/<uuid:ca_id>/verify")
@roles_required(UserRole.ADMIN)
def verify_ca(ca_id):
    """Verify a CA (needs the certificate: 409 CERTIFICATE_MISSING) and email them."""
    profile = get_profile(ca_id)
    if profile.cop_document_id is None:
        raise ApiError(409, "CERTIFICATE_MISSING", "Ask the CA to upload their certificate first.")
    profile.verification_status = CaVerificationStatus.VERIFIED
    profile.verified_at, profile.verified_by_id, profile.rejection_reason = utcnow(), current_user().id, None
    db.session.commit()
    if profile.user.email_notifications:
        send_email(profile.user.email, "Your CA Helper profile is verified", "ca_verified",
                   name=profile.user.full_name)
    return jsonify(ca_to_dict(profile))


@bp.post("/admin/cas/<uuid:ca_id>/reject")
@roles_required(UserRole.ADMIN)
def reject_ca(ca_id):
    """Reject a CA with a reason the CA sees (on their profile page and in an email)."""
    reason = read_text(json_body(), "reason", 500)
    profile = get_profile(ca_id)
    profile.verification_status = CaVerificationStatus.REJECTED
    profile.rejection_reason, profile.verified_at, profile.verified_by_id = reason, None, None
    db.session.commit()
    if profile.user.email_notifications:
        send_email(profile.user.email, "Your CA Helper profile needs a correction", "ca_rejected",
                   name=profile.user.full_name, reason=reason)
    return jsonify(ca_to_dict(profile))
