"""The CA marketplace: CA profiles and prices, Find a CA, requests between a business and a
CA (accept, decline, expiry), ratings, and the access checks that decide what a CA may see
of a business.

Engagement lifecycle: requested -> active (the CA accepts at their listed, fixed prices);
a request can also end declined, expired (48 hours without an answer) or cancelled (the
business withdraws it); active -> completed. A filing is in at most one open engagement
(requested or active).

Verification: a new profile is `pending` until an admin checks it (the Certificate of
Practice must be uploaded first). A new certificate, a changed membership or CoP number,
or any save of a rejected profile sends it back to `pending`. Only verified CAs are listed.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app import alerts, compliance, documents, onboarding
from app.models import (
    CA_LANGUAGES,
    CA_SPECIALIZATIONS,
    SERVICE_SPECIALIZATIONS,
    CaProfile,
    CaService,
    CatalogService,
    CaVerificationStatus,
    ComplianceStatus,
    DocumentType,
    Engagement,
    EngagementItem,
    EngagementStatus,
    FormCode,
    NotificationType,
    Rating,
    User,
    UserRole,
    db,
    utcnow,
)
from app.utils import (
    MISSING,
    ApiError,
    current_business,
    current_user,
    iso,
    json_body,
    login_required,
    money,
    read_page_args,
    read_uuid,
    roles_required,
    send_email,
    validation_error,
)

bp = Blueprint("marketplace", __name__)

# Changing one of these needs a new admin check.
IDENTITY_FIELDS = ("membership_no", "cop_number")
# The typical price range of a service is shown once this many CAs offer it.
MIN_CAS_FOR_RANGE = 3
MAX_PRICE = Decimal(1000000)  # rupees; a higher price is almost certainly a typing mistake
# An engagement in one of these still holds its filings: nobody may request them again.
OPEN_STATUSES = [EngagementStatus.REQUESTED, EngagementStatus.ACTIVE]
# Filings in these states are done: there is nothing left for a CA to do.
FILED_STATUSES = [ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED]
# A CA has this long to answer a request; then the worker marks it `expired`.
ANSWER_WITHIN = timedelta(hours=48)
# How many of a CA's latest reviews the CA page shows.
REVIEWS_SHOWN = 5
# The one catalog service that fits each ITR form, so an ITR filing is only ever priced
# with the service for the business's own form.
ITR_SERVICE_CODES = {
    "itr_3": "itr_business",
    "itr_4": "itr_presumptive",
    "itr_5": "itr_firm_company",
    "itr_6": "itr_firm_company",
}


# --- Reading the request fields ----------------------------------------------------------


def read_int(data, field, lowest, highest, errors, required=True):
    """A whole number between `lowest` and `highest` from a JSON body."""
    value = data.get(field)
    if value is None:
        if required:
            errors[field] = [MISSING]
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        errors[field] = ["Not a valid integer."]
        return None
    if not lowest <= value <= highest:
        errors[field] = [
            f"Must be greater than or equal to {lowest} and less than or equal to {highest}."
        ]
    return value


def read_price(value, lowest):
    """A price in rupees (2 decimals) from `lowest` to MAX_PRICE, or None when it is not one."""
    try:
        if isinstance(value, bool) or value is None:
            return None
        price = Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if not lowest <= price <= MAX_PRICE:
        return None
    return price


def read_code_list(data, field, codes, what, errors):
    """A non-empty list of known codes, stored once each in the order of `codes`."""
    chosen = data.get(field)
    if chosen is None:
        errors[field] = [MISSING]
        return []
    if not isinstance(chosen, list):
        errors[field] = ["Not a valid list."]
        return []
    if len(chosen) == 0:
        errors[field] = [f"Choose at least one {what}."]
    elif any(code not in codes for code in chosen):
        errors[field] = [f"Must be one of: {', '.join(codes)}."]
    return [code for code in codes if code in chosen]


def read_text(data, field, max_length, errors):
    """A required text that is not blank."""
    text = data.get(field)
    if text is None:
        errors[field] = [MISSING]
    elif not isinstance(text, str) or not 1 <= len(text) <= max_length:
        errors[field] = [f"Length must be between 1 and {max_length}."]
    elif not text.strip():
        errors[field] = ["Must not be blank."]
    else:
        return text.strip()
    return None


# --- JSON shapes -------------------------------------------------------------------------


def profile_to_dict(profile):
    """The CA's own profile, with the numbers and the verification status."""
    return {
        "id": str(profile.id),
        "membership_no": profile.membership_no,
        "cop_number": profile.cop_number,
        "city": profile.city,
        "languages": profile.languages,
        "specializations": profile.specializations,
        "capacity": profile.capacity,
        "years_experience": profile.years_experience,
        "about": profile.about,
        "verification_status": profile.verification_status,
        "updated_at": iso(profile.updated_at),
        "rejection_reason": profile.rejection_reason,
        "has_certificate": profile.cop_document_id is not None,
    }


def rating_to_dict(rating):
    """One rating: stars and an optional review. Never shows who wrote it."""
    return {"stars": rating.stars, "review": rating.review, "created_at": iso(rating.created_at)}


def engagement_to_dict(engagement):
    """One engagement as both sides see it: the CA, the business, the filings and prices."""
    ca = db.session.get(CaProfile, engagement.ca_profile_id)
    business = onboarding.get_business(engagement.business_id)
    rows = items_of(engagement)
    filings = compliance.get_filings_by_ids([row.compliance_item_id for row in rows])

    items = []
    for row in rows:
        service = db.session.get(CatalogService, row.service_id)
        filing = filings.get(row.compliance_item_id)  # None if the filing was removed
        items.append(
            {
                "id": str(row.id),
                "compliance_item_id": str(row.compliance_item_id),
                "form_code": filing.form_code if filing else None,
                "period_label": filing.period_label if filing else None,
                "due_date": iso(filing.due_date) if filing else None,
                "service_name": service.name,
                "listed_price": money(row.listed_price),
                "agreed_price": money(row.agreed_price),
            }
        )

    rating = db.session.scalar(select(Rating).where(Rating.engagement_id == engagement.id))
    return {
        "id": str(engagement.id),
        "status": engagement.status,
        "ca_profile_id": str(ca.id),
        "ca_name": ca.user.full_name,
        "business_name": business.legal_name,
        "requested_at": iso(engagement.requested_at),
        "expires_at": iso(engagement.expires_at),
        "responded_at": iso(engagement.responded_at),
        "activated_at": iso(engagement.activated_at),
        "completed_at": iso(engagement.completed_at),
        "items": items,
        "rating": rating_to_dict(rating) if rating else None,
    }


# --- CA profiles ---------------------------------------------------------------------------


def find_profile(user):
    return db.session.scalar(select(CaProfile).where(CaProfile.user_id == user.id))


def get_own_profile(user):
    """The logged-in CA's profile. 404 CA_PROFILE_NOT_FOUND if they have not saved one."""
    profile = find_profile(user)
    if profile is None:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "You have not completed your profile yet.")
    return profile


def own_profile_id(user):
    """The logged-in CA's profile id, or None if they have not saved a profile."""
    profile = find_profile(user)
    return profile.id if profile else None


@bp.get("/marketplace/ca-profile")
@roles_required(UserRole.CA)
def get_my_profile():
    return jsonify(profile_to_dict(get_own_profile(current_user())))


@bp.put("/marketplace/ca-profile")
@roles_required(UserRole.CA)
def save_my_profile():
    """Create or update the CA's profile. 409 DUPLICATE_MEMBERSHIP_NO if another CA uses it."""
    data = json_body()
    errors = {}
    values = {}
    membership_no = data.get("membership_no")
    if membership_no is None:
        errors["membership_no"] = [MISSING]
    elif (
        not isinstance(membership_no, str) or len(membership_no) != 6 or not membership_no.isdigit()
    ):
        errors["membership_no"] = ["Enter your 6-digit ICAI membership number."]
    values["membership_no"] = membership_no
    values["cop_number"] = read_text(data, "cop_number", 20, errors)
    values["city"] = read_text(data, "city", 100, errors)
    values["languages"] = read_code_list(data, "languages", CA_LANGUAGES, "language", errors)
    values["specializations"] = read_code_list(
        data, "specializations", CA_SPECIALIZATIONS, "specialization", errors
    )
    values["capacity"] = read_int(data, "capacity", 1, 1000, errors)
    values["years_experience"] = read_int(data, "years_experience", 0, 70, errors)
    about = data.get("about", "")
    if not isinstance(about, str) or len(about) > 500:
        errors["about"] = ["Longer than maximum length 500."]
    else:
        values["about"] = about.strip()
    if errors:
        raise validation_error(errors)

    user = current_user()
    taken = db.session.scalar(
        select(CaProfile.id).where(
            CaProfile.membership_no == values["membership_no"], CaProfile.user_id != user.id
        )
    )
    if taken:
        raise ApiError(
            409, "DUPLICATE_MEMBERSHIP_NO", "Another CA has already registered this membership number."
        )

    profile = find_profile(user)
    if profile is None:
        profile = CaProfile(user_id=user.id, verification_status=CaVerificationStatus.PENDING)
        db.session.add(profile)
    elif profile.verification_status == CaVerificationStatus.REJECTED or any(
        getattr(profile, name) != values[name] for name in IDENTITY_FIELDS
    ):
        profile.verification_status = CaVerificationStatus.PENDING
    for name, value in values.items():
        if value is not None:
            setattr(profile, name, value)
    db.session.commit()
    return jsonify(profile_to_dict(profile))


@bp.post("/marketplace/ca-profile/certificate")
@roles_required(UserRole.CA)
def upload_certificate():
    """Store the Certificate of Practice; the profile needs a new admin check."""
    upload = request.files.get("file")
    if upload is None:
        raise validation_error({"file": [MISSING]}, "files")
    user = current_user()
    profile = get_own_profile(user)
    document = documents.add_document(user.id, user.id, upload, DocumentType.CERTIFICATE_OF_PRACTICE)
    old_document_id = profile.cop_document_id
    profile.cop_document_id = document.id
    if old_document_id:
        db.session.flush()  # the profile lets go of the old file before it is deleted
        documents.remove_document(old_document_id)
    profile.verification_status = CaVerificationStatus.PENDING
    db.session.commit()
    return jsonify(profile_to_dict(profile))


# --- Find a CA, the catalog and CA prices --------------------------------------------------


def listed_cas():
    """Verified CA profiles (the CAs businesses may see), joined with their users."""
    return (
        select(CaProfile)
        .join(CaProfile.user)
        .where(CaProfile.verification_status == CaVerificationStatus.VERIFIED)
    )


def find_listed_ca(profile_id):
    """A CA businesses may see. 404 CA_NOT_FOUND otherwise."""
    profile = db.session.scalar(listed_cas().where(CaProfile.id == profile_id))
    if profile is None:
        raise ApiError(404, "CA_NOT_FOUND", "This CA is not listed on the marketplace.")
    return profile


def rating_summary(ca_profile_id):
    """{"rating_average": 4.3 (one decimal) or None before any rating, "rating_count": n}."""
    stars = db.session.scalars(
        select(Rating.stars)
        .join(Engagement, Rating.engagement_id == Engagement.id)
        .where(Engagement.ca_profile_id == ca_profile_id)
    ).all()
    if len(stars) == 0:
        return {"rating_average": None, "rating_count": 0}
    return {"rating_average": round(sum(stars) / len(stars), 1), "rating_count": len(stars)}


def list_catalog():
    """Every catalog service with its typical (min, median, max) price."""
    prices = {}  # service id -> [prices of verified CAs]
    stmt = select(CaService.service_id, CaService.price).join(
        CaProfile, CaService.ca_profile_id == CaProfile.id
    )
    stmt = stmt.where(CaProfile.verification_status == CaVerificationStatus.VERIFIED)
    for service_id, price in db.session.execute(stmt):
        prices.setdefault(service_id, []).append(price)

    result = []
    for service in db.session.scalars(select(CatalogService).order_by(CatalogService.sort_order)):
        service_prices = prices.get(service.id, [])
        row = {
            "id": str(service.id),
            "code": service.code,
            "name": service.name,
            "description": service.description,
            "unit": service.unit,
            "specialization": SERVICE_SPECIALIZATIONS.get(service.code),
            "ca_count": len(service_prices),
            "min_price": None,
            "median_price": None,
            "max_price": None,
        }
        if len(service_prices) >= MIN_CAS_FOR_RANGE:
            row["min_price"] = money(min(service_prices))
            row["median_price"] = money(median(service_prices))
            row["max_price"] = money(max(service_prices))
        result.append(row)
    return result


@bp.get("/marketplace/cas")
@roles_required(UserRole.BUSINESS)
def list_cas():
    """Verified CAs with room for clients, best rated first; optional filters."""
    args = request.args
    errors = {}
    page, page_size = read_page_args(errors)
    specialization = args.get("specialization")
    if specialization is not None and specialization not in CA_SPECIALIZATIONS:
        errors["specialization"] = [f"Must be one of: {', '.join(CA_SPECIALIZATIONS)}."]
    language = args.get("language")
    if language is not None and language not in CA_LANGUAGES:
        errors["language"] = [f"Must be one of: {', '.join(CA_LANGUAGES)}."]
    city = args.get("city")
    if city is not None and len(city) > 100:
        errors["city"] = ["Longer than maximum length 100."]
    service = args.get("service")
    if service is not None and len(service) > 50:
        errors["service"] = ["Longer than maximum length 50."]
    if errors:
        raise validation_error(errors, "query")

    stmt = listed_cas()
    if specialization:
        stmt = stmt.where(CaProfile.specializations.contains([specialization]))
    if language:
        stmt = stmt.where(CaProfile.languages.contains([language]))
    if city and city.strip():
        stmt = stmt.where(CaProfile.city.icontains(city.strip(), autoescape=True))
    if service:
        stmt = stmt.join(CaService, CaService.ca_profile_id == CaProfile.id)
        stmt = stmt.join(CatalogService, CaService.service_id == CatalogService.id)
        stmt = stmt.where(CatalogService.code == service)

    rows = []
    for profile in db.session.scalars(stmt):
        if len(active_client_ids(profile.id)) >= profile.capacity:
            continue  # a full CA is hidden
        rows.append((profile, rating_summary(profile.id)))
    # An unrated CA counts as 0 stars.
    rows.sort(
        key=lambda row: (
            -(row[1]["rating_average"] or 0),
            -row[0].years_experience,
            row[0].user.full_name,
        )
    )
    start = (page - 1) * page_size  # e.g. page 2 with page_size 20 is rows 20 to 39

    items = []
    for profile, ratings in rows[start : start + page_size]:
        price = None
        if service:
            price = db.session.scalar(
                select(CaService.price)
                .join(CatalogService, CaService.service_id == CatalogService.id)
                .where(CaService.ca_profile_id == profile.id, CatalogService.code == service)
            )
        items.append(
            {
                "id": str(profile.id),
                "full_name": profile.user.full_name,
                "membership_no": profile.membership_no,
                "city": profile.city,
                "languages": profile.languages,
                "specializations": profile.specializations,
                "years_experience": profile.years_experience,
                "about": profile.about,
                "price": money(price),
                "rating_average": ratings["rating_average"],
                "rating_count": ratings["rating_count"],
            }
        )
    return jsonify({"items": items, "page": page, "page_size": page_size, "total": len(rows)})


@bp.get("/marketplace/cas/<uuid:ca_id>")
@roles_required(UserRole.BUSINESS)
def get_ca(ca_id):
    """One CA's public page: details, services with prices, latest reviews."""
    profile = find_listed_ca(ca_id)
    my_prices = {}
    for row in db.session.scalars(select(CaService).where(CaService.ca_profile_id == profile.id)):
        my_prices[str(row.service_id)] = row.price

    services = []
    for service in list_catalog():
        if service["id"] in my_prices:
            service["price"] = money(my_prices[service["id"]])
            services.append(service)

    latest = db.session.scalars(
        select(Rating)
        .join(Engagement, Rating.engagement_id == Engagement.id)
        .where(Engagement.ca_profile_id == profile.id)
        .order_by(Rating.created_at.desc())
        .limit(REVIEWS_SHOWN)
    )
    ratings = rating_summary(profile.id)
    return jsonify(
        {
            "id": str(profile.id),
            "full_name": profile.user.full_name,
            "membership_no": profile.membership_no,
            "city": profile.city,
            "languages": profile.languages,
            "specializations": profile.specializations,
            "years_experience": profile.years_experience,
            "about": profile.about,
            "services": services,
            "rating_average": ratings["rating_average"],
            "rating_count": ratings["rating_count"],
            "reviews": [rating_to_dict(rating) for rating in latest],
        }
    )


@bp.get("/marketplace/services")
@login_required
def list_services():
    return jsonify(list_catalog())


def menu_of(profile):
    """The services a CA offers now: {"items": [{service_id, price}]}."""
    items = []
    if profile is not None:
        for row in db.session.scalars(select(CaService).where(CaService.ca_profile_id == profile.id)):
            items.append({"service_id": str(row.service_id), "price": money(row.price)})
    return {"items": items}


@bp.get("/marketplace/ca-services")
@roles_required(UserRole.CA)
def get_my_services():
    """The CA's price menu (empty until they have a profile and set prices)."""
    return jsonify(menu_of(find_profile(current_user())))


@bp.put("/marketplace/ca-services")
@roles_required(UserRole.CA)
def save_my_services():
    """Replace the CA's price menu. 400 UNKNOWN_SERVICE."""
    items = json_body().get("items")
    if items is None:
        raise validation_error({"items": [MISSING]})
    if not isinstance(items, list):
        raise validation_error({"items": ["Not a valid list."]})
    new_prices = {}
    for item in items:
        service_id = read_uuid(item.get("service_id")) if isinstance(item, dict) else None
        price = read_price(item.get("price"), 1) if isinstance(item, dict) else None
        if service_id is None or price is None:
            raise validation_error({"items": ["Choose a service and enter a price from 1 to 10,00,000."]})
        new_prices[service_id] = price

    profile = get_own_profile(current_user())
    for service_id in new_prices:
        if db.session.get(CatalogService, service_id) is None:
            raise ApiError(400, "UNKNOWN_SERVICE", "One of the services is not in the catalog.")
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
    return jsonify(menu_of(profile))


# --- Requests and engagements -------------------------------------------------------------


def itr_service_code(business):
    """The catalog code of the ITR service that fits the business's profile."""
    return ITR_SERVICE_CODES.get(onboarding.get_itr_form(business))


def service_fits(service, filing, itr_code):
    """True if `service` is for this filing; for ITR, only the service of the business's form."""
    if service.form_code != filing.form_code:
        return False
    return filing.form_code != FormCode.ITR or service.code == itr_code


def open_filing_ids(filing_ids):
    """The filings among `filing_ids` already in an open engagement."""
    stmt = (
        select(EngagementItem.compliance_item_id)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .where(
            EngagementItem.compliance_item_id.in_(filing_ids),
            Engagement.status.in_(OPEN_STATUSES),
        )
    )
    return set(db.session.scalars(stmt))


def filing_services(ca):
    """The CA's services that are for a filing, as (CatalogService, price) pairs."""
    stmt = (
        select(CatalogService, CaService.price)
        .join(CaService, CaService.service_id == CatalogService.id)
        .where(CaService.ca_profile_id == ca.id, CatalogService.form_code.is_not(None))
        .order_by(CatalogService.sort_order)
    )
    return db.session.execute(stmt).all()


def active_client_ids(ca_profile_id):
    """The businesses the CA has an ACTIVE engagement with."""
    stmt = select(Engagement.business_id).where(
        Engagement.ca_profile_id == ca_profile_id, Engagement.status == EngagementStatus.ACTIVE
    )
    return set(db.session.scalars(stmt))


def check_room(ca, business_id):
    """409 CA_AT_CAPACITY if this business would take the CA over capacity."""
    clients = active_client_ids(ca.id)
    if business_id not in clients and len(clients) >= ca.capacity:
        raise ApiError(
            409,
            "CA_AT_CAPACITY",
            "This CA is not taking new clients right now: all their client slots are full.",
        )


def filing_blocked_reason(filing, busy):
    """Why a filing cannot be given to a CA now, or None if it can."""
    if filing.status in FILED_STATUSES:
        return "Already filed."
    if filing.id in busy:
        return "Already requested from a CA or with a CA."
    return None


def items_of(engagement):
    """The engagement's filings, in the order they were requested."""
    stmt = (
        select(EngagementItem)
        .where(EngagementItem.engagement_id == engagement.id)
        .order_by(EngagementItem.created_at)
    )
    return db.session.scalars(stmt).all()


@bp.get("/marketplace/cas/<uuid:ca_id>/requestable-filings")
@roles_required(UserRole.BUSINESS)
def list_requestable_filings(ca_id):
    """The business's filings with this CA's prices and why one is blocked."""
    business = current_business()
    ca = find_listed_ca(ca_id)
    services = filing_services(ca)
    itr_code = itr_service_code(business)
    filings = compliance.list_filings(business)
    busy = open_filing_ids([filing.id for filing in filings])

    result = []
    for filing in filings:
        options = []
        for service, price in services:
            if service_fits(service, filing, itr_code):
                options.append({"service_id": str(service.id), "name": service.name, "price": money(price)})
        blocked_reason = filing_blocked_reason(filing, busy)
        if blocked_reason is None and len(options) == 0:
            if filing.form_code == FormCode.ITR:
                blocked_reason = "This CA has not listed a price for the ITR of your business type."
            else:
                blocked_reason = "This CA has not listed a price for this filing."
        result.append(
            {
                "id": str(filing.id),
                "form_code": filing.form_code,
                "period_label": filing.period_label,
                "due_date": iso(filing.due_date),
                "status": filing.status,
                "options": options,
                "blocked_reason": blocked_reason,
            }
        )
    return jsonify(result)


@bp.post("/marketplace/engagements")
@roles_required(UserRole.BUSINESS)
def send_request():
    """Ask a CA to do some filings at their listed prices; the CA is told."""
    data = json_body()
    errors = {}
    ca_profile_id = data.get("ca_profile_id")
    if ca_profile_id is None:
        errors["ca_profile_id"] = [MISSING]
    elif read_uuid(ca_profile_id) is None:
        errors["ca_profile_id"] = ["Not a valid UUID."]
    items = data.get("items")
    if items is None:
        errors["items"] = [MISSING]
    elif not isinstance(items, list) or len(items) == 0:
        errors["items"] = ["Choose at least one filing."]
    else:
        for item in items:
            if not isinstance(item, dict) or None in (
                read_uuid(item.get("compliance_item_id")),
                read_uuid(item.get("service_id")),
            ):
                errors["items"] = ["Each filing needs a compliance_item_id and a service_id."]
    if errors:
        raise validation_error(errors)

    business = current_business()
    ca = find_listed_ca(read_uuid(ca_profile_id))
    check_room(ca, business.id)
    itr_code = itr_service_code(business)
    chosen = {}  # filing id -> the service chosen for it
    for item in items:
        filing_id = read_uuid(item["compliance_item_id"])
        if filing_id in chosen:
            raise ApiError(400, "DUPLICATE_FILING", "The same filing is in the request twice.")
        chosen[filing_id] = read_uuid(item["service_id"])

    filings = compliance.get_filings_by_ids(list(chosen))
    busy = open_filing_ids(list(chosen))
    offered = {service.id: (service, price) for service, price in filing_services(ca)}
    for filing_id, service_id in chosen.items():
        filing = filings.get(filing_id)
        if filing is None or filing.business_id != business.id:
            raise ApiError(404, "FILING_NOT_FOUND", "One of the filings was not found.")
        if filing.status in FILED_STATUSES:
            raise ApiError(409, "FILING_ALREADY_FILED", f"{filing.period_label} is already filed.")
        if filing_id in busy:
            raise ApiError(
                409,
                "FILING_ALREADY_REQUESTED",
                f"{filing.period_label} is already requested from a CA or with a CA.",
            )
        if service_id not in offered or not service_fits(offered[service_id][0], filing, itr_code):
            raise ApiError(
                400, "SERVICE_NOT_OFFERED", "This CA does not offer that service for this filing."
            )

    now = utcnow()
    engagement = Engagement(
        business_id=business.id,
        ca_profile_id=ca.id,
        status=EngagementStatus.REQUESTED,
        requested_at=now,
        expires_at=now + ANSWER_WITHIN,
    )
    db.session.add(engagement)
    db.session.flush()  # gives engagement.id
    for filing_id, service_id in chosen.items():
        db.session.add(
            EngagementItem(
                engagement_id=engagement.id,
                compliance_item_id=filing_id,
                service_id=service_id,
                listed_price=offered[service_id][1],
            )
        )
    alerts.notify(
        ca.user,
        NotificationType.ENGAGEMENT_UPDATE,
        f"New request from {business.legal_name}",
        f"{business.legal_name} asked you to handle {len(chosen)} filing(s). "
        "Answer within 48 hours.",
        "/ca/engagements",
    )
    db.session.commit()
    if ca.user.email_notifications:
        send_email(
            ca.user.email,
            "New request on CA Helper",
            "engagement_requested",
            ca_name=ca.user.full_name,
            business_name=business.legal_name,
            filing_count=len(chosen),
        )
    return jsonify(engagement_to_dict(engagement)), 201


def engagements_where(condition):
    """The engagements matching `condition`, newest first, as JSON."""
    stmt = select(Engagement).where(condition).order_by(Engagement.requested_at.desc())
    return [engagement_to_dict(engagement) for engagement in db.session.scalars(stmt)]


@bp.get("/marketplace/my-engagements")
@roles_required(UserRole.BUSINESS)
def list_my_engagements():
    """Every engagement of the business, newest first."""
    return jsonify(engagements_where(Engagement.business_id == current_business().id))


@bp.get("/marketplace/ca-engagements")
@roles_required(UserRole.CA)
def list_ca_engagements():
    """Every engagement of the CA, newest first (empty without a profile)."""
    ca = find_profile(current_user())
    if ca is None:
        return jsonify([])
    return jsonify(engagements_where(Engagement.ca_profile_id == ca.id))


# --- Answering a request ---------------------------------------------------------------------


def ca_engagement(engagement_id):
    """One of the logged-in CA's engagements. 404 ENGAGEMENT_NOT_FOUND for anyone else's."""
    engagement = db.session.get(Engagement, engagement_id)
    ca = find_profile(current_user())
    if engagement is None or ca is None or engagement.ca_profile_id != ca.id:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    return engagement


def business_engagement(engagement_id):
    """One of the logged-in business's engagements. 404 ENGAGEMENT_NOT_FOUND otherwise."""
    engagement = db.session.get(Engagement, engagement_id)
    if engagement is None or engagement.business_id != current_business().id:
        raise ApiError(404, "ENGAGEMENT_NOT_FOUND", "This engagement was not found.")
    return engagement


def check_status(engagement, expected):
    """409 INVALID_STATUS unless the engagement is in the `expected` status."""
    if engagement.status != expected:
        raise ApiError(
            409,
            "INVALID_STATUS",
            f"This engagement is {engagement.status}, so this is no longer possible.",
        )


def check_not_expired(engagement):
    """409 REQUEST_EXPIRED once the 48 hours to answer have passed."""
    if engagement.expires_at is not None and engagement.expires_at <= utcnow():
        raise ApiError(
            409, "REQUEST_EXPIRED", "This request expired: it was not answered within 48 hours."
        )


def activate(engagement, items):
    """Start the work: status `active`, and the filings are "With CA"."""
    engagement.status = EngagementStatus.ACTIVE
    engagement.activated_at = utcnow()
    compliance.mark_filings_with_ca([item.compliance_item_id for item in items])


def notify_business(engagement, title, text):
    """A tray entry for the business owner: the CA's name followed by `text`."""
    business = onboarding.get_business(engagement.business_id)
    ca = db.session.get(CaProfile, engagement.ca_profile_id)
    alerts.notify(
        db.session.get(User, business.user_id),
        NotificationType.ENGAGEMENT_UPDATE,
        title,
        f"{ca.user.full_name} {text}",
        "/business/engagements",
    )


def email_business(engagement, subject, template, **context):
    """Email the business owner, if they want emails (call after the commit)."""
    business = onboarding.get_business(engagement.business_id)
    owner = db.session.get(User, business.user_id)
    if not owner.email_notifications:
        return
    ca = db.session.get(CaProfile, engagement.ca_profile_id)
    send_email(
        owner.email, subject, template, owner_name=owner.full_name, ca_name=ca.user.full_name, **context
    )


@bp.post("/marketplace/engagements/<uuid:engagement_id>/accept")
@roles_required(UserRole.CA)
def accept_request(engagement_id):
    """The CA accepts at the listed prices: status `active`."""
    engagement = ca_engagement(engagement_id)
    check_status(engagement, EngagementStatus.REQUESTED)
    check_not_expired(engagement)
    check_room(db.session.get(CaProfile, engagement.ca_profile_id), engagement.business_id)
    items = items_of(engagement)
    for item in items:
        item.agreed_price = item.listed_price
    engagement.responded_at = utcnow()
    activate(engagement, items)
    notify_business(
        engagement,
        "Your CA accepted your request",
        "accepted your request at their listed prices. The work has started.",
    )
    db.session.commit()
    email_business(engagement, "Your CA accepted your request", "engagement_accepted")
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/decline")
@roles_required(UserRole.CA)
def decline_request(engagement_id):
    """The CA declines: status `declined`; the filings are free to request again."""
    engagement = ca_engagement(engagement_id)
    check_status(engagement, EngagementStatus.REQUESTED)
    check_not_expired(engagement)
    engagement.status = EngagementStatus.DECLINED
    engagement.responded_at = utcnow()
    notify_business(
        engagement,
        "Your CA declined your request",
        'declined your request. You can ask another CA in "Find a CA".',
    )
    db.session.commit()
    email_business(engagement, "Your CA declined your request", "engagement_declined")
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/complete")
@roles_required(UserRole.CA)
def complete_engagement(engagement_id):
    """The CA marks the work as done: status `completed`."""
    engagement = ca_engagement(engagement_id)
    check_status(engagement, EngagementStatus.ACTIVE)
    engagement.status = EngagementStatus.COMPLETED
    engagement.completed_at = utcnow()
    notify_business(
        engagement,
        "Your CA completed the work",
        'marked the work as completed. You can rate it in "My engagements".',
    )
    db.session.commit()
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/withdraw")
@roles_required(UserRole.BUSINESS)
def withdraw_request(engagement_id):
    """The business withdraws a request the CA has not answered: status `cancelled`."""
    engagement = business_engagement(engagement_id)
    check_status(engagement, EngagementStatus.REQUESTED)
    engagement.status = EngagementStatus.CANCELLED
    db.session.commit()
    return jsonify(engagement_to_dict(engagement))


@bp.post("/marketplace/engagements/<uuid:engagement_id>/rating")
@roles_required(UserRole.BUSINESS)
def rate_engagement(engagement_id):
    """The business rates a completed engagement once: 1 to 5 stars and an optional review."""
    data = json_body()
    errors = {}
    stars = data.get("stars")
    if stars is None:
        errors["stars"] = [MISSING]
    elif isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        errors["stars"] = ["Choose 1 to 5 stars."]
    review = data.get("review", "")
    if not isinstance(review, str) or len(review) > 2000:
        errors["review"] = ["Longer than maximum length 2000."]
    if errors:
        raise validation_error(errors)

    engagement = business_engagement(engagement_id)
    check_status(engagement, EngagementStatus.COMPLETED)
    if db.session.scalar(select(Rating.id).where(Rating.engagement_id == engagement.id)):
        raise ApiError(409, "ALREADY_RATED", "You have already rated this CA for this work.")
    db.session.add(Rating(engagement_id=engagement.id, stars=stars, review=review.strip() or None))
    db.session.commit()
    return jsonify(engagement_to_dict(engagement))


def expire_old_requests():
    """Expire requests not answered within 48 hours; returns how many (worker job)."""
    stmt = select(Engagement).where(
        Engagement.status == EngagementStatus.REQUESTED, Engagement.expires_at <= utcnow()
    )
    expired = db.session.scalars(stmt).all()
    for engagement in expired:
        engagement.status = EngagementStatus.EXPIRED
        notify_business(
            engagement,
            "Your CA request expired",
            f"did not answer within 48 hours. Choose another CA for: {service_names(engagement)}.",
        )
    db.session.commit()
    for engagement in expired:
        email_business(
            engagement,
            "Your CA request expired",
            "engagement_expired",
            service_names=service_names(engagement),
        )
    return len(expired)


def service_names(engagement):
    """The services of an engagement, e.g. "GSTR-3B filing, GSTR-1 filing"."""
    names = []
    for item in items_of(engagement):
        name = db.session.get(CatalogService, item.service_id).name
        if name not in names:
            names.append(name)
    return ", ".join(names)


# --- Access checks: what a CA may see of a business ----------------------------------------
# Only an ACTIVE engagement gives access to the business's data, and only to its filings.
# After the engagement ends, the CA sees nothing of that business any more.


def ca_can_see_business(ca_profile_id, business_id):
    """True while the CA has an ACTIVE engagement with the business."""
    stmt = select(Engagement.id).where(
        Engagement.ca_profile_id == ca_profile_id,
        Engagement.business_id == business_id,
        Engagement.status == EngagementStatus.ACTIVE,
    )
    return db.session.scalar(stmt) is not None


def ca_can_open_document(ca_profile_id, document_id):
    """True only for a document of a filing in one of the CA's active engagements."""
    stmt = (
        select(EngagementItem.compliance_item_id)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .where(Engagement.ca_profile_id == ca_profile_id, Engagement.status == EngagementStatus.ACTIVE)
    )
    filing_ids = set(db.session.scalars(stmt))
    if len(filing_ids) == 0:
        return False
    allowed = documents.document_ids_for_filings(filing_ids)
    for filing in compliance.get_filings_by_ids(filing_ids).values():
        if filing.acknowledgement_document_id is not None:
            allowed.add(filing.acknowledgement_document_id)
    return document_id in allowed


# --- For other modules -------------------------------------------------------------------


def active_ca_users_by_filing(filing_ids):
    """{filing id: the CA's User} for the filings in an ACTIVE engagement (reminders)."""
    if len(filing_ids) == 0:
        return {}
    stmt = (
        select(EngagementItem.compliance_item_id, User)
        .join(Engagement, EngagementItem.engagement_id == Engagement.id)
        .join(CaProfile, Engagement.ca_profile_id == CaProfile.id)
        .join(User, CaProfile.user_id == User.id)
        .where(
            EngagementItem.compliance_item_id.in_(filing_ids),
            Engagement.status == EngagementStatus.ACTIVE,
        )
    )
    return {filing_id: user for filing_id, user in db.session.execute(stmt)}


def active_work(ca_profile_id):
    """(engagement id, business id, filing id) for every filing in the CA's ACTIVE engagements."""
    stmt = (
        select(Engagement.id, Engagement.business_id, EngagementItem.compliance_item_id)
        .join(EngagementItem, EngagementItem.engagement_id == Engagement.id)
        .where(Engagement.ca_profile_id == ca_profile_id, Engagement.status == EngagementStatus.ACTIVE)
    )
    return [tuple(row) for row in db.session.execute(stmt)]


def active_cas_of_business(business_id):
    """{engagement id: the CA's User} for the business's ACTIVE engagements."""
    stmt = (
        select(Engagement.id, User)
        .join(CaProfile, Engagement.ca_profile_id == CaProfile.id)
        .join(User, CaProfile.user_id == User.id)
        .where(Engagement.business_id == business_id, Engagement.status == EngagementStatus.ACTIVE)
    )
    return {engagement_id: user for engagement_id, user in db.session.execute(stmt)}


def complete_if_all_filed(engagement_id):
    """Complete an active engagement once all its filings are filed."""
    engagement = db.session.get(Engagement, engagement_id)
    if engagement is None or engagement.status != EngagementStatus.ACTIVE:
        return False
    filings = compliance.get_filings_by_ids([item.compliance_item_id for item in items_of(engagement)])
    for filing in filings.values():
        if filing.status not in FILED_STATUSES:
            return False
    engagement.status = EngagementStatus.COMPLETED
    engagement.completed_at = utcnow()
    notify_business(
        engagement,
        "Your CA completed the work",
        'filed every filing of your request. You can rate the work in "My engagements".',
    )
    return True


def admin_row(profile):
    """Everything an admin sees about a CA (their numbers too, for checking)."""
    return {
        **profile_to_dict(profile),
        "user_id": str(profile.user_id),
        "full_name": profile.user.full_name,
        "email": profile.user.email,
        "verified_at": iso(profile.verified_at),
    }


def list_cas_for_admin(status):
    """CA profiles (optionally of one status), the longest-waiting first."""
    stmt = select(CaProfile).order_by(CaProfile.updated_at)
    if status is not None:
        stmt = stmt.where(CaProfile.verification_status == status)
    return [admin_row(profile) for profile in db.session.scalars(stmt)]


def ca_for_admin(profile_id):
    profile = db.session.get(CaProfile, profile_id)
    if profile is None:
        raise ApiError(404, "CA_NOT_FOUND", "This CA was not found.")
    return profile


def get_ca_for_admin(profile_id):
    return admin_row(ca_for_admin(profile_id))


def certificate_document_id(profile_id):
    """The document id of the CA's Certificate of Practice. 404 CERTIFICATE_MISSING."""
    profile = ca_for_admin(profile_id)
    if profile.cop_document_id is None:
        raise ApiError(404, "CERTIFICATE_MISSING", "This CA has not uploaded a certificate.")
    return profile.cop_document_id


def set_verification(profile_id, admin, verified, reason):
    """An admin verifies (needs the certificate) or rejects a CA."""
    profile = ca_for_admin(profile_id)
    if verified:
        if profile.cop_document_id is None:
            raise ApiError(409, "CERTIFICATE_MISSING", "Ask the CA to upload their certificate first.")
        profile.verification_status = CaVerificationStatus.VERIFIED
        profile.verified_at = utcnow()
        profile.verified_by_id = admin.id
        profile.rejection_reason = None
    else:
        profile.verification_status = CaVerificationStatus.REJECTED
        profile.rejection_reason = reason
        profile.verified_at = None
        profile.verified_by_id = None
    return profile


def count_cas_by_status():
    """{"pending": n, "verified": n, "rejected": n} over all CA profiles."""
    counts = {"pending": 0, "verified": 0, "rejected": 0}
    for status in db.session.scalars(select(CaProfile.verification_status)):
        counts[status] += 1
    return counts


def count_open_engagements():
    stmt = select(func.count()).select_from(Engagement).where(Engagement.status.in_(OPEN_STATUSES))
    return db.session.scalar(stmt)
