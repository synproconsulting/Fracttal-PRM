import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
)
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    role = Column(String, nullable=False, default="partner_user")
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_role = Column(String, nullable=False)
    action = Column(String, nullable=False)
    object_type = Column(String, nullable=False)
    object_id = Column(Uuid(as_uuid=True), nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    notes = Column(String, nullable=True)


class ProgramType(str, enum.Enum):
    distributor = "distributor"
    subpartner = "subpartner"


class PartnerCategory(str, enum.Enum):
    master = "master"
    promotor = "promotor"
    reseller = "reseller"


class PartnerTier(str, enum.Enum):
    registered = "registered"
    silver = "silver"
    gold = "gold"


class PartnerStatus(str, enum.Enum):
    applicant = "applicant"
    active = "active"
    suspended = "suspended"
    inactive = "inactive"
    terminated = "terminated"


class MonthlyFeeStatus(str, enum.Enum):
    current = "current"
    overdue = "overdue"
    waived = "waived"


class PartnerOrganization(Base):
    __tablename__ = "partner_organizations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name = Column(String, nullable=False)
    dba_name = Column(String, nullable=True)
    website = Column(String, nullable=True)
    hq_address = Column(JSON, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    program_type = Column(SAEnum(ProgramType, name="program_type"), nullable=False)
    partner_category = Column(SAEnum(PartnerCategory, name="partner_category"), nullable=False)
    parent_partner_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=True,
    )
    tier = Column(SAEnum(PartnerTier, name="partner_tier"), nullable=True)
    territory = Column(JSON, nullable=True)
    industries = Column(JSON, nullable=True)
    authorized_offerings = Column(JSON, nullable=True)
    delivery_capabilities = Column(JSON, nullable=True)
    status = Column(
        SAEnum(PartnerStatus, name="partner_status"),
        nullable=False,
        default=PartnerStatus.applicant,
    )
    monthly_fee_status = Column(
        SAEnum(MonthlyFeeStatus, name="monthly_fee_status"),
        nullable=False,
        default=MonthlyFeeStatus.current,
    )
    contract_start_date = Column(Date, nullable=True)
    contract_end_date = Column(Date, nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)
    certification_expiry_date = Column(Date, nullable=True)
    hubspot_company_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DocumentType(str, enum.Enum):
    id_legal_representative = "id_legal_representative"
    power_of_attorney = "power_of_attorney"
    articles_of_incorporation = "articles_of_incorporation"
    beneficial_owners_list = "beneficial_owners_list"
    fiscal_id = "fiscal_id"
    proof_of_fiscal_domicile = "proof_of_fiscal_domicile"
    bank_certificate = "bank_certificate"
    nda = "nda"
    insurance = "insurance"
    other = "other"


class DocumentStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class DocumentTypeConfig(Base):
    """Sprint 9 / FPRM-144 — admin-configurable document type vocabulary.

    Seeded with the original 10 enum values from migration 005. Upload validation
    in ``documents_router.upload_document`` queries this table by ``code`` rather
    than the legacy ``DocumentType`` enum, so a system_admin can introduce new
    document categories at runtime via POST /config/document-types.
    """

    __tablename__ = "document_types"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PartnerDocument(Base):
    __tablename__ = "partner_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=False,
    )
    # FPRM-144: stored as plain VARCHAR (migration 017 converted the PG enum).
    # Values validated against the document_types config table at upload time.
    document_type = Column(String, nullable=False)
    document_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    uploaded_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = Column(Date, nullable=True)
    status = Column(
        SAEnum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.pending_review,
    )
    review_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    info_request_message = Column(Text, nullable=True)


class InvitedRole(str, enum.Enum):
    partner_user = "partner_user"
    partner_admin = "partner_admin"


class PartnerUserInvite(Base):
    __tablename__ = "partner_user_invites"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=False,
    )
    email = Column(String, nullable=False)
    invited_role = Column(SAEnum(InvitedRole, name="invited_role"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    invited_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActivityType(str, enum.Enum):
    note = "note"
    task = "task"
    call = "call"
    meeting = "meeting"
    email = "email"
    status_change = "status_change"


class PartnerActivity(Base):
    __tablename__ = "partner_activities"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=False,
    )
    activity_type = Column(SAEnum(ActivityType, name="activity_type"), nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assigned_to_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_internal = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CommissionType(str, enum.Enum):
    autonomous_sell = "autonomous_sell"
    indirect_sell = "indirect_sell"
    direct_sell = "direct_sell"
    co_sell_shared = "co_sell_shared"


class CommissionYear(str, enum.Enum):
    year_1 = "year_1"
    year_2_plus = "year_2_plus"


class PartnerCategoryConfig(Base):
    __tablename__ = "partner_category_configs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    deal_reg_sla_hours = Column(Integer, nullable=False)
    max_discount_pct = Column(Numeric, nullable=False)
    monthly_fee_usd = Column(Numeric, default=200, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CommissionStructure(Base):
    __tablename__ = "commission_structures"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_category_code = Column(
        String,
        ForeignKey("partner_category_configs.code"),
        nullable=False,
    )
    commission_type = Column(String, nullable=False)
    year = Column(SAEnum(CommissionYear, name="commission_year"), nullable=False)
    commission_pct = Column(Numeric, nullable=False)
    subpartner_uplift_pct = Column(Numeric, default=10.0, nullable=False)
    applies_to_upsell = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    info_required = "info_required"
    approved = "approved"
    rejected = "rejected"


class PartnerApplication(Base):
    __tablename__ = "partner_applications"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(
        SAEnum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.draft,
    )
    applicant_email = Column(String, nullable=False)
    applicant_name = Column(String, nullable=True)
    applicant_phone = Column(String, nullable=True)
    applicant_title = Column(String, nullable=True)
    legal_name = Column(String, nullable=True)
    dba_name = Column(String, nullable=True)
    website = Column(String, nullable=True)
    hq_address = Column(JSON, nullable=True)
    phone = Column(String, nullable=True)
    requested_categories = Column(JSON, nullable=True)
    territory = Column(JSON, nullable=True)
    industries = Column(JSON, nullable=True)
    year_established = Column(Integer, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue = Column(String, nullable=True)
    shareholders = Column(JSON, nullable=True)
    other_software_products = Column(Text, nullable=True)
    cmms_experience = Column(Boolean, nullable=True)
    cmms_experience_description = Column(Text, nullable=True)
    sales_marketing_strategy = Column(Text, nullable=True)
    technical_support_team = Column(Boolean, nullable=True)
    technical_support_description = Column(Text, nullable=True)
    implementation_services = Column(Boolean, nullable=True)
    implementation_description = Column(Text, nullable=True)
    partnership_goals = Column(Text, nullable=True)
    market_growth_plan = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    references = Column(JSON, nullable=True)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    terms_accepted_at = Column(DateTime, nullable=True)
    draft_token = Column(String, unique=True, nullable=True, index=True)
    draft_expires_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    reviewer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PartnerApplicationDocument(Base):
    __tablename__ = "partner_application_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_applications.id"),
        nullable=False,
        index=True,
    )
    document_type = Column(String, nullable=False)
    document_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        unique=True,
        nullable=False,
    )
    year_established = Column(Integer, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue = Column(String, nullable=True)
    shareholders = Column(JSON, nullable=True)
    cmms_experience = Column(Boolean, nullable=True)
    cmms_experience_description = Column(Text, nullable=True)
    other_software_products = Column(Text, nullable=True)
    sales_marketing_strategy = Column(Text, nullable=True)
    technical_support_team = Column(Boolean, nullable=True)
    technical_support_description = Column(Text, nullable=True)
    implementation_services = Column(Boolean, nullable=True)
    implementation_description = Column(Text, nullable=True)
    partnership_goals = Column(Text, nullable=True)
    market_growth_plan = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    profile_completeness_pct = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ApplicationMessageSender(str, enum.Enum):
    applicant = "applicant"
    internal = "internal"


class PartnerApplicationMessage(Base):
    __tablename__ = "partner_application_messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_applications.id"),
        nullable=False,
        index=True,
    )
    sender_type = Column(
        SAEnum(ApplicationMessageSender, name="application_message_sender"),
        nullable=False,
    )
    sender_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sender_email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PartnerActivationChecklist(Base):
    __tablename__ = "partner_activation_checklists"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        unique=True,
        nullable=False,
    )
    profile_complete = Column(Boolean, default=False, nullable=False)
    documents_uploaded = Column(Boolean, default=False, nullable=False)
    terms_signed = Column(Boolean, default=False, nullable=False)
    baseline_training_complete = Column(Boolean, default=False, nullable=False)
    activation_complete = Column(Boolean, default=False, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DealRegistration(Base):
    """Sprint 8 / FPRM-125 — deal opportunities registered by partner_admins.

    Lifecycle: draft -> submitted -> under_review -> approved | rejected | expired.
    Commission rate is snapshotted from ``commission_structures`` at submission
    time (immutable thereafter); conflict status is populated by the Sprint 10
    conflict checker (defaults to ``not_checked``).
    """

    __tablename__ = "deal_registrations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=False,
    )
    status = Column(String, nullable=False, default="draft")

    # Customer info
    customer_name = Column(String, nullable=False)
    customer_domain = Column(String, nullable=True)
    customer_contact_name = Column(String, nullable=True)
    customer_contact_email = Column(String, nullable=True)
    customer_contact_phone = Column(String, nullable=True)
    customer_industry = Column(String, nullable=True)
    customer_country = Column(String, nullable=True)
    customer_region = Column(String, nullable=True)

    # Deal info
    deal_name = Column(String, nullable=False)
    estimated_deal_value = Column(Float, nullable=True)
    estimated_close_date = Column(Date, nullable=True)
    deal_notes = Column(Text, nullable=True)
    commission_type = Column(String, nullable=True)

    # Commission snapshot (set at submission; immutable after)
    commission_structure_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("commission_structures.id"),
        nullable=True,
    )
    commission_rate_snapshot = Column(Float, nullable=True)

    # Conflict check (Sprint 10 populates these; Sprint 8 leaves them as defaults)
    conflict_checked_at = Column(DateTime, nullable=True)
    conflict_status = Column(String, nullable=False, default="not_checked")
    conflict_notes = Column(Text, nullable=True)

    # Lifecycle + reviewer
    submitted_at = Column(DateTime, nullable=True)
    reviewer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_deal_registrations_partner_status", "partner_org_id", "status"),
    )


class DealMessage(Base):
    """Sprint 9 / FPRM-139 — collaboration thread on a deal registration.

    Mirrors the PartnerApplicationMessage pattern (Sprint 6 / AD-12 sibling).
    ``sender_type`` is ``partner`` or ``internal``; ``sender_id`` references
    the authenticated user and is always populated (no anonymous thread posts).
    """

    __tablename__ = "deal_messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("deal_registrations.id"),
        nullable=False,
    )
    sender_type = Column(String, nullable=False)  # "partner" | "internal"
    sender_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sender_email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_deal_messages_deal_created", "deal_id", "created_at"),
    )
