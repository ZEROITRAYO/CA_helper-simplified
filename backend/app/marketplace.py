"""The CA marketplace: CA profiles and prices, Find a CA, requests between a business and a
CA (accept, decline, withdraw), ratings, and the access checks that decide what a CA may see
of a business.

Engagement lifecycle: requested -> active (the CA accepts at their listed, fixed prices);
a request can also end declined (by the CA) or cancelled (the business withdraws it); it never
expires on its own; active -> completed. A filing is in at most one open engagement
(requested or active).

Verification: a new profile is `pending` until an admin checks it (the Certificate of
Practice must be uploaded first). A new certificate, a changed membership or CoP number,
or any save of a rejected profile sends it back to `pending`. Only verified CAs are listed.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app import alerts, compliance, documents
from app.models import (
    CA_LANGUAGES, CA_SPECIALIZATIONS, SERVICE_SPECIALIZATIONS, CaProfile, CaService,
    CatalogService, CaVerificationStatus, ComplianceStatus, DocumentType, Engagement,
    EngagementItem, EngagementStatus, FilingPath, FormCode, NotificationType, Rating, RegulatoryProfile, User,
    UserRole, db, utcnow,
)
from app.utils import (
    MISSING, ApiError, current_business, current_user, invalid, iso, json_body, login_required,
    money, page_args, read_amount, read_choice, read_id, read_int, read_text, read_uuid, roles_required,
    send_email,
)

bp = Blueprint("marketplace", __name__)

# Filings in these states are done: there is nothing left for a CA to do.
FILED_STATUSES = [ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED]
# The one catalog service that fits each ITR form, so an ITR filing is only ever priced
# with the service for the business's own form.
ITR_SERVICE_CODES = {
    "itr_3": "itr_business", "itr_4": "itr_presumptive", "itr_5": "itr_firm_company",
    "itr_6": "itr_firm_company",
}


def profile_to_dict(profile):
    """The CA's own profile, with the numbers and the verification status."""
    return {
        "id": str(profile.id), "membership_no": profile.membership_no,
        "cop_number": profile.cop_number, "city": profile.city, "languages": profile.languages,
        "specializations": profile.specializations, "capacity": profile.capacity,
        "years_experience": profile.years_experience, "about": profile.about,
        "verification_status": profile.verification_status, "updated_at": iso(profile.updated_at),
        "rejection_reason": profile.rejection_reason,
        "has_certificate": profile.cop_document_id is not None,
    }


def rating_to_dict(rating):
    """One rating: stars and an optional review. Never shows who wrote it."""
    return {"stars": rating.stars, "review": rating.review, "created_at": iso(rating.created_at)}


def items_of(engagement):
    """The engagement's filings, in the order they were requested."""
    return db.session.scalars(
        select(EngagementItem).where(EngagementItem.engagement_id == engagement.id)
        .order_by(EngagementItem.created_at)
    ).all()


def engagement_to_dict(engagement):
    """One engagement as both sides see it: the CA, the business, the filings and prices."""
    items = []
    for row in items_of(engagement):
        filing = row.filing  # None if the filing was removed
        items.append({
            "id": str(row.id), "compliance_item_id": str(row.compliance_item_id),
            "form_code": filing.form_code if filing else None,
            "period_label": filing.period_label if filing else None,
            "due_date": iso(filing.due_date) if filing else None, "service_name": row.service.name,
            "listed_price": money(row.listed_price), "agreed_price": money(row.agreed_price),
        })
    rating = db.session.scalar(select(Rating).where(Rating.engagement_id == engagement.id))
    return {
        "id": str(engagement.id), "status": engagement.status,
        "ca_profile_id": str(engagement.ca_profile_id), "ca_name": engagement.ca.user.full_name,
        "business_name": engagement.business.legal_name,
        "requested_at": iso(engagement.requested_at), "responded_at": iso(engagement.responded_at),
        "activated_at": iso(engagement.activated_at), "completed_at": iso(engagement.completed_at),
        "items": items, "rating": rating_to_dict(rating) if rating else None,
    }


# --- CA profiles ---------------------------------------------------------------------------


def own_profile(user, required=True):
    """The logged-in CA's profile. 404 CA_PROFILE_NOT_FOUND if they have not saved one."""
    profile = db.session.scalar(select(CaProfile).where(CaProfile.user_id == user.id))
    if profile is None and required:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "You have not completed your profile yet.")
    return profile


def read_codes(data, field, codes, what):
    """A non-empty list of known codes, stored once each in the order of `codes`."""
    chosen = data.get(field)
    if chosen is None:
        raise invalid(field, MISSING)
    if not isinstance(chosen, list) or len(chosen) == 0:
        raise invalid(field, f"Choose at least one {what}.")
    if any(code not in codes for code in chosen):
        raise invalid(field, f"Must be one of: {', '.join(codes)}.")
    return [code for code in codes if code in chosen]


@bp.get("/marketplace/ca-profile")
@roles_required(UserRole.CA)
def get_my_profile():
    return jsonify(profile_to_dict(own_profile(current_user())))


@bp.put("/marketplace/ca-profile")
@roles_required(UserRole.CA)
def save_my_profile():
    """Create or update the CA's profile. 409 DUPLICATE_MEMBERSHIP_NO if another CA uses it."""
    data = json_body()
    membership_no = data.get("membership_no")
    if not isinstance(membership_no, str) or len(membership_no) != 6 or not membership_no.isdigit():
        raise invalid("membership_no", "Enter your 6-digit ICAI membership number.")
    about = data.get("about", "")
    if not isinstance(about, str) or len(about) > 500:
        raise invalid("about", "Longer than maximum length 500.")
    values = {
        "membership_no": membership_no,
        "cop_number": read_text(data, "cop_number", 20),
        "city": read_text(data, "city", 100),
        "languages": read_codes(data, "languages", CA_LANGUAGES, "language"),
        "specializations": read_codes(data, "specializations", CA_SPECIALIZATIONS, "specialization"),
        "capacity": read_int(data, "capacity", 1, 1000),
        "years_experience": read_int(data, "years_experience", 0, 70),
        "about": about.strip(),
    }
    user = current_user()
    if db.session.scalar(select(CaProfile.id).where(
        CaProfile.membership_no == membership_no, CaProfile.user_id != user.id
    )):
        raise ApiError(409, "DUPLICATE_MEMBERSHIP_NO",
                       "Another CA has already registered this membership number.")
    profile = own_profile(user, required=False)
    if profile is None:
        profile = CaProfile(user_id=user.id)
        db.session.add(profile)
    # Changing the membership or CoP number, or saving a rejected profile, needs a new admin check.
    if (profile.verification_status == CaVerificationStatus.REJECTED
            or profile.membership_no != membership_no or profile.cop_number != values["cop_number"]):
        profile.verification_status = CaVerificationStatus.PENDING
    for name, value in values.items():
        setattr(profile, name, value)
    db.session.commit()
    return jsonify(profile_to_dict(profile))


@bp.post("/marketplace/ca-profile/certificate")
@roles_required(UserRole.CA)
def upload_certificate():
    """Store the Certificate of Practice; the profile needs a new admin check."""
    user = current_user()
    profile = own_profile(user)
    old_document_id = profile.cop_document_id
    certificate = documents.add_document(user.id, user.id, DocumentType.CERTIFICATE_OF_PRACTICE)
    profile.cop_document_id = certificate.id
    if old_document_id:
        db.session.flush()  # the profile lets go of the old file before it is deleted
        documents.remove_document(old_document_id)
    profile.verification_status = CaVerificationStatus.PENDING
    db.session.commit()
    return jsonify(profile_to_dict(profile))


# --- Find a CA, the catalog and CA prices --------------------------------------------------


def find_listed_ca(profile_id):
    """A verified CA (one businesses may see). 404 CA_NOT_FOUND otherwise."""
    profile = db.session.get(CaProfile, profile_id) if profile_id else None
    if profile is None or profile.verification_status != CaVerificationStatus.VERIFIED:
        raise ApiError(404, "CA_NOT_FOUND", "This CA is not listed on the marketplace.")
    return profile


def ratings_of(ca_profile_id):
    """The CA's ratings, newest first."""
    return db.session.scalars(
        select(Rating).join(Engagement).where(Engagement.ca_profile_id == ca_profile_id)
        .order_by(Rating.created_at.desc())
    ).all()


def public_ca(profile):
    """What a business sees of a CA, with "rating_average" (one decimal, None before any
    rating) and "rating_count"."""
    stars = [rating.stars for rating in ratings_of(profile.id)]
    return {
        "id": str(profile.id), "full_name": profile.user.full_name,
        "membership_no": profile.membership_no, "city": profile.city,
        "languages": profile.languages, "specializations": profile.specializations,
        "years_experience": profile.years_experience, "about": profile.about,
        "rating_average": round(sum(stars) / len(stars), 1) if stars else None,
        "rating_count": len(stars),
    }


def list_catalog():
    """Every catalog service, in catalog order."""
    return [
        {"id": str(service.id), "code": service.code, "name": service.name,
         "description": service.description, "unit": service.unit,
         "specialization": SERVICE_SPECIALIZATIONS.get(service.code)}
        for service in db.session.scalars(select(CatalogService).order_by(CatalogService.sort_order))
    ]


def prices_of(profile):
    """{service id (text): price} of the services a CA offers."""
    rows = db.session.scalars(select(CaService).where(CaService.ca_profile_id == profile.id))
    return {str(row.service_id): row.price for row in rows}


def active_client_ids(ca_profile_id):
    """The businesses the CA has an ACTIVE engagement with."""
    return set(db.session.scalars(select(Engagement.business_id).where(
        Engagement.ca_profile_id == ca_profile_id, Engagement.status == EngagementStatus.ACTIVE
    )))


@bp.get("/marketplace/cas")
@roles_required(UserRole.BUSINESS)
def list_cas():
    """Verified CAs with room for clients, best rated first; optional filters."""
    args = request.args
    stmt = select(CaProfile).join(CaProfile.user).where(
        CaProfile.verification_status == CaVerificationStatus.VERIFIED
    )
    if args.get("specialization"):
        stmt = stmt.where(CaProfile.specializations.contains(
            [read_choice(args, "specialization", CA_SPECIALIZATIONS, location="query")]
        ))
    if args.get("language"):
        stmt = stmt.where(CaProfile.languages.contains(
            [read_choice(args, "language", CA_LANGUAGES, location="query")]
        ))
    if args.get("city", "").strip():
        stmt = stmt.where(CaProfile.city.icontains(args["city"].strip()[:100], autoescape=True))
    service = db.session.scalar(select(CatalogService).where(CatalogService.code == args.get("service")))
    if args.get("service"):
        stmt = stmt.join(CaService).where(CaService.service_id == (service.id if service else None))

    rows = []
    for profile in db.session.scalars(stmt):
        if len(active_client_ids(profile.id)) < profile.capacity:  # a full CA is hidden
            row = public_ca(profile)
            row["price"] = money(prices_of(profile).get(str(service.id))) if service else None
            rows.append(row)
    # An unrated CA counts as 0 stars.
    rows.sort(key=lambda row: (-(row["rating_average"] or 0), -row["years_experience"], row["full_name"]))
    page, page_size = page_args()
    start = (page - 1) * page_size  # e.g. page 2 with page_size 20 is rows 20 to 39
    return jsonify({"items": rows[start:start + page_size], "page": page, "page_size": page_size,
                    "total": len(rows)})


@bp.get("/marketplace/cas/<uuid:ca_id>")
@roles_required(UserRole.BUSINESS)
def get_ca(ca_id):
    """One CA's public page: details, services with prices, the latest 5 reviews."""
    profile = find_listed_ca(ca_id)
    prices = prices_of(profile)
    services = [{**s, "price": money(prices[s["id"]])} for s in list_catalog() if s["id"] in prices]
    page = public_ca(profile)
    page.update(services=services, reviews=[rating_to_dict(r) for r in ratings_of(profile.id)[:5]])
    return jsonify(page)


@bp.get("/marketplace/services")
@login_required
def list_services():
    return jsonify(list_catalog())


@bp.route("/marketplace/ca-services", methods=["GET", "PUT"])
@roles_required(UserRole.CA)
def my_services():
    """The CA's price menu {"items": [{service_id, price}]}; PUT replaces it. 400 UNKNOWN_SERVICE."""
    profile = own_profile(current_user(), required=request.method == "PUT")
    if request.method == "PUT":
        items = json_body().get("items")
        if not isinstance(items, list):
            raise invalid("items", MISSING if items is None else "Not a valid list.")
        new_prices = {}
        for item in items:
            item = item if isinstance(item, dict) else {}
            service_id, price = read_uuid(item.get("service_id")), read_amount(item.get("price"), 1, 1000000)
            if service_id is None or price is None:
                raise invalid("items", "Choose a service and enter a price from 1 to 10,00,000.")
            if db.session.get(CatalogService, service_id) is None:
                raise ApiError(400, "UNKNOWN_SERVICE", "One of the services is not in the catalog.")
            new_prices[service_id] = price
        # Update the rows the CA already has; delete the ones left out.
        for row in db.session.scalars(select(CaService).where(CaService.ca_profile_id == profile.id)):
            if row.service_id in new_prices:
                row.price = new_prices.pop(row.service_id)
            else:
                db.session.delete(row)
        # Whatever is left is offered for the first time.
        for service_id, price in new_prices.items():
            db.session.add(CaService(ca_profile_id=profile.id, service_id=service_id, price=price))
        db.session.commit()
    prices = prices_of(profile) if profile else {}
    return jsonify({"items": [{"service_id": sid, "price": money(p)} for sid, p in prices.items()]})


# --- Requests and engagements -------------------------------------------------------------


def filing_services(ca, business):
    """The CA's services that are for a filing, as (CatalogService, price) pairs, and a check
    service_fits(service, filing): for ITR, only the service of the business's own ITR form."""
    profile = db.session.scalar(select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id))
    itr_code = ITR_SERVICE_CODES.get(profile.itr_form if profile else None)
    services = db.session.execute(
        select(CatalogService, CaService.price).join(CaService, CaService.service_id == CatalogService.id)
        .where(CaService.ca_profile_id == ca.id, CatalogService.form_code.is_not(None))
        .order_by(CatalogService.sort_order)
    ).all()

    def service_fits(service, filing):
        if service.form_code != filing.form_code:
            return False
        return filing.form_code != FormCode.ITR or service.code == itr_code

    return services, service_fits


def check_room(ca, business_id):
    """409 CA_AT_CAPACITY if this business would take the CA over capacity."""
    clients = active_client_ids(ca.id)
    if business_id not in clients and len(clients) >= ca.capacity:
        raise ApiError(409, "CA_AT_CAPACITY",
                       "This CA is not taking new clients right now: all their client slots are full.")


@bp.get("/marketplace/cas/<uuid:ca_id>/requestable-filings")
@roles_required(UserRole.BUSINESS)
def list_requestable_filings(ca_id):
    """The business's filings with this CA's prices and why one is blocked."""
    business = current_business()
    services, service_fits = filing_services(find_listed_ca(ca_id), business)
    filings = compliance.list_filings(business)
    busy = compliance.open_filing_ids([filing.id for filing in filings])
    result = []
    for filing in filings:
        options = [
            {"service_id": str(service.id), "name": service.name, "price": money(price)}
            for service, price in services if service_fits(service, filing)
        ]
        # Why a filing cannot be given to this CA now, or None if it can.
        blocked_reason = None
        if filing.status in FILED_STATUSES:
            blocked_reason = "Already filed."
        elif filing.id in busy:
            blocked_reason = "Already requested from a CA or with a CA."
        elif not options and filing.form_code == FormCode.ITR:
            blocked_reason = "This CA has not listed a price for the ITR of your business type."
        elif not options:
            blocked_reason = "This CA has not listed a price for this filing."
        result.append({
            "id": str(filing.id), "form_code": filing.form_code, "period_label": filing.period_label,
            "due_date": iso(filing.due_date), "status": filing.status, "options": options,
            "blocked_reason": blocked_reason,
        })
    return jsonify(result)


@bp.post("/marketplace/engagements")
@roles_required(UserRole.BUSINESS)
def send_request():
    """Ask a CA to do some filings at their listed prices; the CA is told."""
    data = json_body()
    ca_id = read_id(data, "ca_profile_id")
    items = data.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise invalid("items", MISSING if items is None else "Choose at least one filing.")
    chosen = {}  # filing id -> the service chosen for it
    for item in items:
        item = item if isinstance(item, dict) else {}
        filing_id, service_id = read_uuid(item.get("compliance_item_id")), read_uuid(item.get("service_id"))
        if None in (filing_id, service_id):
            raise invalid("items", "Each filing needs a compliance_item_id and a service_id.")
        if filing_id in chosen:
            raise ApiError(400, "DUPLICATE_FILING", "The same filing is in the request twice.")
        chosen[filing_id] = service_id

    business = current_business()
    ca = find_listed_ca(ca_id)
    check_room(ca, business.id)
    services, service_fits = filing_services(ca, business)
    offered = {service.id: (service, price) for service, price in services}
    filings = compliance.get_filings_by_ids(list(chosen))
    busy = compliance.open_filing_ids(list(chosen))
    for filing_id, service_id in chosen.items():
        filing = filings.get(filing_id)
        if filing is None or filing.business_id != business.id:
            raise ApiError(404, "FILING_NOT_FOUND", "One of the filings was not found.")
        if filing.status in FILED_STATUSES:
            raise ApiError(409, "FILING_ALREADY_FILED", f"{filing.period_label} is already filed.")
        if filing_id in busy:
            raise ApiError(409, "FILING_ALREADY_REQUESTED",
                           f"{filing.period_label} is already requested from a CA or with a CA.")
        if service_id not in offered or not service_fits(offered[service_id][0], filing):
            raise ApiError(400, "SERVICE_NOT_OFFERED", "This CA does not offer that service for this filing.")

    engagement = Engagement(business_id=business.id, ca_profile_id=ca.id, requested_at=utcnow())
    db.session.add(engagement)
    db.session.flush()  # gives engagement.id
    for filing_id, service_id in chosen.items():
        db.session.add(EngagementItem(engagement_id=engagement.id, compliance_item_id=filing_id,
                                      service_id=service_id, listed_price=offered[service_id][1]))
    alerts.notify(ca.user, NotificationType.ENGAGEMENT_UPDATE, f"New request from {business.legal_name}",
                  f"{business.legal_name} asked you to handle {len(chosen)} filing(s). Accept or decline it.",
                  "/ca/engagements")
    db.session.commit()
    if ca.user.email_notifications:
        send_email(ca.user.email, "New request on CA Helper", "engagement_requested",
                   ca_name=ca.user.full_name, business_name=business.legal_name, filing_count=len(chosen))
    return jsonify(engagement_to_dict(engagement)), 201


def engagements_where(condition):
    """The engagements matching `condition`, newest first, as JSON."""
    stmt = select(Engagement).where(condition).order_by(Engagement.requested_at.desc())
    return jsonify([engagement_to_dict(engagement) for engagement in db.session.scalars(stmt)])


@bp.get("/marketplace/my-engagements")
@roles_required(UserRole.BUSINESS)
def list_my_engagements():
    """Every engagement of the business, newest first."""
    return engagements_where(Engagement.business_id == current_business().id)


@bp.get("/marketplace/ca-engagements")
@roles_required(UserRole.CA)
def list_ca_engagements():
    """Every engagement of the CA, newest first (empty without a profile)."""
    ca = own_profile(current_user(), required=False)
    return engagements_where(Engagement.ca_profile_id == (ca.id if ca else None))


# --- Answering a request ---------------------------------------------------------------------


def my_engagement(engagement_id, expected_status):
    """One of the logged-in CA's or business's engagements (404 ENGAGEMENT_NOT_FOUND for
    anyone else's), in the `expected_status` (409 INVALID_STATUS otherwise)."""
    engagement = db.session.get(Engagement, engagement_id)
    user = current_user()
    if engagement is None:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    owner = engagement.ca.user_id if user.role == UserRole.CA else engagement.business.user_id
    if owner != user.id:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    if engagement.status != expected_status:
        raise ApiError(409, "INVALID_STATUS",
                       f"This engagement is {engagement.status}, so this is no longer possible.")
    return engagement


def tell_business(engagement, title, text, template=None):
    """A tray entry for the business owner (the CA's name followed by `text`), the commit,
    then the email if there is one and the owner wants emails."""
    owner = db.session.get(User, engagement.business.user_id)
    ca_name = engagement.ca.user.full_name
    alerts.notify(owner, NotificationType.ENGAGEMENT_UPDATE, title, f"{ca_name} {text}",
                  "/business/engagements")
    db.session.commit()
    if template and owner.email_notifications:
        send_email(owner.email, title, template, owner_name=owner.full_name, ca_name=ca_name)
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/accept")
@roles_required(UserRole.CA)
def accept_request(engagement_id):
    """The CA accepts at the listed prices: status `active`, and the filings are "With CA"."""
    engagement = my_engagement(engagement_id, EngagementStatus.REQUESTED)
    check_room(engagement.ca, engagement.business_id)
    for item in items_of(engagement):
        item.agreed_price = item.listed_price
        item.filing.status, item.filing.filing_path = ComplianceStatus.WITH_CA, FilingPath.CA
    engagement.status = EngagementStatus.ACTIVE
    engagement.responded_at = engagement.activated_at = utcnow()
    return tell_business(engagement, "Your CA accepted your request",
                         "accepted your request at their listed prices. The work has started.",
                         "engagement_accepted")


@bp.post("/marketplace/engagements/<uuid:engagement_id>/decline")
@roles_required(UserRole.CA)
def decline_request(engagement_id):
    """The CA declines: status `declined`; the filings are free to request again."""
    engagement = my_engagement(engagement_id, EngagementStatus.REQUESTED)
    engagement.status = EngagementStatus.DECLINED
    engagement.responded_at = utcnow()
    return tell_business(engagement, "Your CA declined your request",
                         'declined your request. You can ask another CA in "Find a CA".',
                         "engagement_declined")


@bp.post("/marketplace/engagements/<uuid:engagement_id>/complete")
@roles_required(UserRole.CA)
def complete_engagement(engagement_id):
    """The CA marks the work as done: status `completed`."""
    engagement = my_engagement(engagement_id, EngagementStatus.ACTIVE)
    engagement.status = EngagementStatus.COMPLETED
    engagement.completed_at = utcnow()
    return tell_business(engagement, "Your CA completed the work",
                         'marked the work as completed. You can rate it in "My engagements".')


@bp.post("/marketplace/engagements/<uuid:engagement_id>/withdraw")
@roles_required(UserRole.BUSINESS)
def withdraw_request(engagement_id):
    """The business withdraws a request the CA has not answered: status `cancelled`."""
    engagement = my_engagement(engagement_id, EngagementStatus.REQUESTED)
    engagement.status = EngagementStatus.CANCELLED
    alerts.notify(engagement.ca.user, NotificationType.ENGAGEMENT_UPDATE,
                  f"{engagement.business.legal_name} withdrew their request",
                  "You do not need to answer it any more.", "/ca/engagements")
    db.session.commit()
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/rating")
@roles_required(UserRole.BUSINESS)
def rate_engagement(engagement_id):
    """The business rates a completed engagement once: 1 to 5 stars and an optional review."""
    data = json_body()
    stars = data.get("stars")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        raise invalid("stars", MISSING if stars is None else "Choose 1 to 5 stars.")
    review = data.get("review", "")
    if not isinstance(review, str) or len(review) > 2000:
        raise invalid("review", "Longer than maximum length 2000.")
    engagement = my_engagement(engagement_id, EngagementStatus.COMPLETED)
    if db.session.scalar(select(Rating.id).where(Rating.engagement_id == engagement.id)):
        raise ApiError(409, "ALREADY_RATED", "You have already rated this CA for this work.")
    db.session.add(Rating(engagement_id=engagement.id, stars=stars, review=review.strip() or None))
    db.session.commit()
    return jsonify(engagement_to_dict(engagement))


# --- Access checks: what a CA may see of a business ----------------------------------------
# Only an ACTIVE engagement gives access to the business's data, and only to its filings.
# After the engagement ends, the CA sees nothing of that business any more.


def active_items(ca_profile_id):
    """The (engagement, item) pairs of the CA's ACTIVE engagements."""
    return db.session.execute(
        select(Engagement, EngagementItem).join(EngagementItem)
        .where(Engagement.ca_profile_id == ca_profile_id, Engagement.status == EngagementStatus.ACTIVE)
    ).all()


def ca_can_see_business(ca_profile_id, business_id):
    """True while the CA has an ACTIVE engagement with the business."""
    return business_id in active_client_ids(ca_profile_id)


def ca_can_open_document(ca_profile_id, document_id):
    """True only for a document of a filing in one of the CA's active engagements."""
    for _, item in active_items(ca_profile_id):
        filing_documents = documents.documents_by_filing([item.filing])[item.filing.id]
        if str(document_id) in [file["document_id"] for file in filing_documents]:
            return True
    return False


def complete_if_all_filed(engagement):
    """Complete an active engagement once all its filings are filed (no commit)."""
    if any(item.filing.status not in FILED_STATUSES for item in items_of(engagement)):
        return False
    engagement.status = EngagementStatus.COMPLETED
    engagement.completed_at = utcnow()
    alerts.notify(db.session.get(User, engagement.business.user_id), NotificationType.ENGAGEMENT_UPDATE,
                  "Your CA completed the work",
                  f'{engagement.ca.user.full_name} filed every filing of your request. You can rate '
                  'the work in "My engagements".', "/business/engagements")
    return True
