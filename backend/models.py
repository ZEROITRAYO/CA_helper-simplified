# The database tables. Every table has an id (UUID), created_at and updated_at.
# PAN, GSTIN, TAN and phone numbers are stored encrypted (EncryptedText below).

import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class EncryptedText(db.TypeDecorator):
    """A text column that is encrypted before it is saved and decrypted when it is read."""

    impl = db.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return Fernet(current_app.config["FIELD_ENCRYPTION_KEY"]).encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Fernet(current_app.config["FIELD_ENCRYPTION_KEY"]).decrypt(value.encode()).decode()


class Table(db.Model):
    """The columns every table has."""

    __abstract__ = True
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now)


# --- Accounts ---


class User(Table):
    __tablename__ = "users"
    email = db.Column(db.String(254), unique=True)  # always lowercase
    password_hash = db.Column(db.String(255))
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(50))  # "business", "ca" or "admin"
    email_verified_at = db.Column(db.DateTime(timezone=True))  # login is refused until it is set
    terms_accepted_at = db.Column(db.DateTime(timezone=True))
    email_notifications = db.Column(db.Boolean, default=True)


class EmailOtp(Table):
    """A 6-digit code emailed to a user (only its hash is stored)."""

    __tablename__ = "email_otps"
    user_id = db.Column(db.Uuid, db.ForeignKey("users.id"))
    purpose = db.Column(db.String(50))  # "verify_email" or "reset_password"
    code_hash = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime(timezone=True))
    used_at = db.Column(db.DateTime(timezone=True))


# --- Businesses ---


class NicCode(Table):
    """One activity code from the official NIC list."""

    __tablename__ = "nic_codes"
    code = db.Column(db.String(10), unique=True)
    description = db.Column(db.String(500))


class Business(Table):
    __tablename__ = "businesses"
    user_id = db.Column(db.Uuid, db.ForeignKey("users.id"), unique=True)
    legal_name = db.Column(db.String(200))
    entity_type = db.Column(db.String(50))  # individual, proprietorship, partnership, llp, private_limited
    state = db.Column(db.String(50))
    address = db.Column(db.String(500))
    description = db.Column(db.String(1000))
    annual_turnover = db.Column(db.Numeric(12, 2))
    investment_amount = db.Column(db.Numeric(12, 2))
    pan = db.Column(EncryptedText)
    phone = db.Column(EncryptedText)
    gst_registered = db.Column(db.Boolean)
    gstin = db.Column(EncryptedText)
    gst_composition = db.Column(db.Boolean, default=False)
    gst_qrmp = db.Column(db.Boolean, default=False)  # quarterly GST returns
    accounts_audited_other_law = db.Column(db.Boolean, default=False)
    deducts_tds = db.Column(db.Boolean)
    tan = db.Column(EncryptedText)
    pays_salary_above_limit = db.Column(db.Boolean)
    cin_llpin = db.Column(db.String(21))
    udyam_number = db.Column(db.String(19))
    nic_code_id = db.Column(db.Uuid, db.ForeignKey("nic_codes.id"))


class RegulatoryProfile(Table):
    """What the rules say about one business (worked out when it registers or edits)."""

    __tablename__ = "regulatory_profiles"
    business_id = db.Column(db.Uuid, db.ForeignKey("businesses.id"), unique=True)
    msme_tier = db.Column(db.String(50))
    gst_scheme = db.Column(db.String(50))
    gst_registration_suggested = db.Column(db.Boolean)
    itr_form = db.Column(db.String(50))
    presumptive_eligible = db.Column(db.Boolean)
    audit_applicable = db.Column(db.Boolean)
    other_audit_applicable = db.Column(db.Boolean, default=False)
    files_24q = db.Column(db.Boolean)
    files_26q = db.Column(db.Boolean)
    roc_not_tracked = db.Column(db.Boolean)
    explanations = db.Column(JSONB)
    rule_version = db.Column(db.String(50))
    computed_at = db.Column(db.DateTime(timezone=True))


class RuleThreshold(Table):
    """A legal limit, e.g. the GST registration turnover (filled by seed.py)."""

    __tablename__ = "rule_thresholds"
    key = db.Column(db.String(100))
    value = db.Column(db.Numeric(18, 4))
    unit = db.Column(db.String(20))
    description = db.Column(db.String(500))
    source_reference = db.Column(db.String(500))
    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)


# --- Filings ---


class ObligationTemplate(Table):
    """Which businesses must file a form and when it is due (filled by seed.py)."""

    __tablename__ = "obligation_templates"
    form_code = db.Column(db.String(50))
    name = db.Column(db.String(100))
    frequency = db.Column(db.String(50))  # monthly, quarterly or yearly
    applicability = db.Column(JSONB)  # e.g. {"gst_scheme": ["regular_monthly"]}
    due_date_rule = db.Column(JSONB)  # e.g. {"day": 11}
    source_reference = db.Column(db.String(500))
    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)


class ComplianceItem(Table):
    """One filing of one business, e.g. GSTR-3B for April 2026."""

    __tablename__ = "compliance_items"
    business_id = db.Column(db.Uuid, db.ForeignKey("businesses.id"))
    template_id = db.Column(db.Uuid, db.ForeignKey("obligation_templates.id"))
    form_code = db.Column(db.String(50))
    fy = db.Column(db.String(7))  # financial year, e.g. "2026-27"
    period_label = db.Column(db.String(30))  # e.g. "Apr 2026" or "Q1 2026-27"
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    due_date = db.Column(db.Date)
    # upcoming, docs_pending, ready, with_ca, filed, filed_verified or overdue
    status = db.Column(db.String(50), default="upcoming")
    filing_path = db.Column(db.String(50))  # "self" or "ca"
    filed_at = db.Column(db.DateTime(timezone=True))
    acknowledgement_no = db.Column(db.String(50))
    verified_at = db.Column(db.DateTime(timezone=True))
    acknowledgement_document_id = db.Column(db.Uuid, db.ForeignKey("documents.id"))


class ChecklistTick(Table):
    __tablename__ = "checklist_ticks"
    compliance_item_id = db.Column(db.Uuid, db.ForeignKey("compliance_items.id"))
    checklist_key = db.Column(db.String(50))


class PenaltyRule(Table):
    """Late fee and interest of one form (filled by seed.py; empty = not confirmed yet)."""

    __tablename__ = "penalty_rules"
    form_code = db.Column(db.String(50))
    late_fee_per_day = db.Column(db.Numeric(12, 2))
    max_late_fee = db.Column(db.Numeric(12, 2))
    flat_late_fee = db.Column(db.Numeric(12, 2))
    annual_interest_rate = db.Column(db.Numeric(5, 2))
    source_reference = db.Column(db.String(500))
    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)


class ReminderLog(Table):
    """A reminder already sent for a filing, so it is never sent twice."""

    __tablename__ = "reminder_log"
    compliance_item_id = db.Column(db.Uuid, db.ForeignKey("compliance_items.id"))
    kind = db.Column(db.String(50))  # t_minus_7, t_minus_3, t_minus_1 or overdue
    sent_at = db.Column(db.DateTime(timezone=True))


class Notification(Table):
    __tablename__ = "notifications"
    user_id = db.Column(db.Uuid, db.ForeignKey("users.id"))
    type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    body = db.Column(db.String(2000))
    link = db.Column(db.String(300))
    read_at = db.Column(db.DateTime(timezone=True))


# --- Documents ---


class Document(Table):
    """An uploaded file; the file itself is stored encrypted in `content`."""

    __tablename__ = "documents"
    owner_id = db.Column(db.Uuid, db.ForeignKey("users.id"))
    uploaded_by_id = db.Column(db.Uuid, db.ForeignKey("users.id"))
    doc_type = db.Column(db.String(50))
    original_filename = db.Column(db.String(255))
    content = db.deferred(db.Column(db.LargeBinary))  # loaded only when the file is opened
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.Integer)
    sha256 = db.Column(db.String(64))
    fy = db.Column(db.String(7))
    period_label = db.Column(db.String(30))
    ocr_status = db.Column(db.String(50), default="none")  # none, processed or failed
    ocr_fields = db.Column(JSONB)  # what OCR read (never personal data)


class ComplianceItemDocument(Table):
    """A document linked to a filing, for one checklist entry (or "general")."""

    __tablename__ = "compliance_item_documents"
    compliance_item_id = db.Column(db.Uuid, db.ForeignKey("compliance_items.id"))
    document_id = db.Column(db.Uuid, db.ForeignKey("documents.id"))
    checklist_key = db.Column(db.String(50), default="general")
    linked_by_id = db.Column(db.Uuid, db.ForeignKey("users.id"))


# --- CAs and engagements ---


class CaProfile(Table):
    __tablename__ = "ca_profiles"
    user_id = db.Column(db.Uuid, db.ForeignKey("users.id"), unique=True)
    user = db.relationship("User", foreign_keys=[user_id])
    membership_no = db.Column(db.String(6), unique=True)
    cop_number = db.Column(db.String(20))
    city = db.Column(db.String(100))
    languages = db.Column(ARRAY(db.String(50)))
    specializations = db.Column(ARRAY(db.String(50)))
    capacity = db.Column(db.Integer)  # most clients at the same time
    years_experience = db.Column(db.Integer)
    about = db.Column(db.String(500), default="")
    verification_status = db.Column(db.String(50), default="pending")  # pending, verified, rejected
    rejection_reason = db.Column(db.String(500))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = db.Column(db.Uuid, db.ForeignKey("users.id"))
    cop_document_id = db.Column(db.Uuid, db.ForeignKey("documents.id"))  # the certificate


class CatalogService(Table):
    """A standard service, e.g. "GSTR-3B filing" (filled by seed.py)."""

    __tablename__ = "service_catalog"
    code = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(300))
    unit = db.Column(db.String(50))
    sort_order = db.Column(db.Integer)
    form_code = db.Column(db.String(50))  # empty for services that are not a filing


class CaService(Table):
    """One CA's price for one catalog service."""

    __tablename__ = "ca_services"
    ca_profile_id = db.Column(db.Uuid, db.ForeignKey("ca_profiles.id"))
    service_id = db.Column(db.Uuid, db.ForeignKey("service_catalog.id"))
    price = db.Column(db.Numeric(12, 2))


class Engagement(Table):
    """A business working with a CA: requested, active, completed, declined or cancelled."""

    __tablename__ = "engagements"
    business_id = db.Column(db.Uuid, db.ForeignKey("businesses.id"))
    business = db.relationship("Business")
    ca_profile_id = db.Column(db.Uuid, db.ForeignKey("ca_profiles.id"))
    ca = db.relationship("CaProfile")
    status = db.Column(db.String(50), default="requested")
    requested_at = db.Column(db.DateTime(timezone=True), default=now)
    responded_at = db.Column(db.DateTime(timezone=True))
    activated_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))


class EngagementItem(Table):
    """One filing in an engagement, with the service and its price."""

    __tablename__ = "engagement_items"
    engagement_id = db.Column(db.Uuid, db.ForeignKey("engagements.id"))
    compliance_item_id = db.Column(db.Uuid, db.ForeignKey("compliance_items.id"))
    filing = db.relationship("ComplianceItem")
    service_id = db.Column(db.Uuid, db.ForeignKey("service_catalog.id"))
    service = db.relationship("CatalogService")
    listed_price = db.Column(db.Numeric(12, 2))
    agreed_price = db.Column(db.Numeric(12, 2))


class Rating(Table):
    __tablename__ = "ratings"
    engagement_id = db.Column(db.Uuid, db.ForeignKey("engagements.id"), unique=True)
    stars = db.Column(db.SmallInteger)
    review = db.Column(db.String(2000))


class DocumentRequest(Table):
    """A CA asking the business for a document (open, fulfilled or cancelled)."""

    __tablename__ = "document_requests"
    engagement_id = db.Column(db.Uuid, db.ForeignKey("engagements.id"))
    engagement = db.relationship("Engagement")
    compliance_item_id = db.Column(db.Uuid, db.ForeignKey("compliance_items.id"))
    filing = db.relationship("ComplianceItem")
    checklist_key = db.Column(db.String(50))
    message = db.Column(db.String(1000))
    status = db.Column(db.String(50), default="open")
    fulfilled_at = db.Column(db.DateTime(timezone=True))
    document_id = db.Column(db.Uuid, db.ForeignKey("documents.id"))
