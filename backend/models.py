import enum

import uuid

from datetime import datetime
from decimal import Decimal

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

    UniqueConstraint,

    Uuid,

)

from sqlalchemy.orm import relationship

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

    customer_contact_position = Column(String, nullable=True)

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



    # Sprint 20 / FPRM-315 (Phase 6) -- Section A additional prospect/engagement fields
    engagement_date = Column(Date, nullable=True)
    prospect_phone = Column(String, nullable=True)
    compiled_by = Column(String, nullable=True)
    prospect_contact_name = Column(String, nullable=True)
    prospect_contact_position = Column(String, nullable=True)
    prospect_website = Column(String, nullable=True)
    industry_sector = Column(String, nullable=True)
    company_size = Column(String, nullable=True)  # "1-10" | "11-50" | "51-200" | "201-500" | "500+"
    feature_plan_preference = Column(String, nullable=True)  # "starter" | "professional" | "enterprise"

    # Sprint 20 / FPRM-315 -- Section B Current State (Situation -- what they have)
    current_system = Column(String, nullable=True)  # none|excel|paper|social_media|cmms|other
    old_system = Column(String, nullable=True)
    inventory_stores = Column(String, nullable=True)
    work_orders_prs = Column(String, nullable=True)
    monitoring_system = Column(String, nullable=True)

    # Sprint 20 / FPRM-315 -- Section B Feature requirements (Yes/No)
    need_asset_depreciation = Column(Boolean, nullable=True)
    need_wo_wr = Column(Boolean, nullable=True)
    need_reports = Column(Boolean, nullable=True)
    need_tool_management = Column(Boolean, nullable=True)
    need_purchasing = Column(Boolean, nullable=True)
    need_integration = Column(Boolean, nullable=True)
    integration_with = Column(String, nullable=True)
    need_multi_language = Column(Boolean, nullable=True)
    languages_required = Column(String, nullable=True)
    need_asset_management = Column(Boolean, nullable=True)
    need_document_management = Column(Boolean, nullable=True)
    need_cost_tracking = Column(Boolean, nullable=True)
    need_monitoring = Column(Boolean, nullable=True)
    need_schedule_third_parties = Column(Boolean, nullable=True)
    need_track_labour = Column(Boolean, nullable=True)

    # Sprint 20 / FPRM-315 -- Section B SPICED narrative fields
    about_client = Column(Text, nullable=True)
    pain = Column(Text, nullable=True)
    impact = Column(Text, nullable=True)
    critical_event = Column(Text, nullable=True)
    decision = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)

    # Sprint 20 / FPRM-317 -- Internal deal creation flag (True when an internal user created the deal on behalf of a partner)
    created_on_behalf_of = Column(Boolean, default=False, nullable=False)

    # Post-Sprint 20 (Phase 6) deal form fix -- partners capture requested
    # license counts on the deal. Migration 029. Nullable for backward
    # compatibility with deals registered before the column existed.
    qty_transactional_users = Column(Integer, nullable=True)
    qty_limited_tech_users = Column(Integer, nullable=True)

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





class ApprovalWorkflowStep(Base):

    """Sprint 13 / FPRM-209 — configurable approval steps for partner application

    and deal registration review.



    Phase 4 introduces *configuration* only; enforcement (routing through

    sequential approvers) is deferred to Phase 5. The seeded rows in migration

    021 mirror the current hardcoded behaviour (one Channel Ops Review step

    for partner applications, one Channel Manager Review step for deal

    registrations).

    """



    __tablename__ = "approval_workflow_steps"



    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workflow_type = Column(String, nullable=False)  # "partner_application" | "deal_registration"

    step_order = Column(Integer, nullable=False)

    step_name = Column(String, nullable=False)

    required_role = Column(String, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)




class ApprovalStepRecord(Base):
    """FPRM-274 / Sprint 17 - audit trail of per-step approval actions.

    One row per approve/reject action taken on a workflow object. The
    ``object_id`` is polymorphic - it points at ``partner_applications.id``
    or ``deal_registrations.id`` depending on ``workflow_type``. There is no
    FK constraint on it (a union-typed FK would require non-portable
    triggers); the index is the access path for back-references. The
    ``step_name`` and ``required_role`` columns snapshot the configured
    workflow at the time of action so historical records survive future
    edits to ``approval_workflow_steps``.
    """

    __tablename__ = "approval_step_records"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_type = Column(String, nullable=False)
    object_id = Column(Uuid(as_uuid=True), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_name = Column(String, nullable=False)
    required_role = Column(String, nullable=False)
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    actioned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_approval_step_records_object_id", "object_id"),
        Index(
            "ix_approval_step_records_workflow_object",
            "workflow_type",
            "object_id",
        ),
    )





class PartnerTierConfig(Base):

    """Sprint 13 / FPRM-213 — configurable partner-tier records.



    Named ``PartnerTierConfig`` to avoid a class-name clash with the existing

    ``PartnerTier`` enum (registered / silver / gold) that ``partner_organizations.tier``

    still references. The table itself is named ``partner_tiers`` because it is

    the configurable replacement for that enum; Phase 5 will migrate the

    foreign-key relationship and the enum will be retired.



    Seeded with three rows in migration 022: Registered (1), Silver (2), Gold (3).

    """



    __tablename__ = "partner_tiers"



    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tier_name = Column(String, unique=True, nullable=False)

    tier_rank = Column(Integer, nullable=False)

    description = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)



    eligibility_rules = relationship(

        "PartnerTierEligibilityRule",

        back_populates="tier",

        cascade="all, delete-orphan",

    )





class PartnerTierEligibilityRule(Base):

    """Sprint 13 / FPRM-213 — eligibility criteria attached to a partner tier.



    A tier can hold zero or more rules. Each rule is a (rule_type, rule_value)

    tuple — the value is stored as a string so the same column can hold

    integers, percentages, or certification codes; the rule_type discriminator

    tells callers how to interpret it.



    Valid ``rule_type`` values: ``min_deals_approved``, ``min_revenue``,

    ``required_certification``, ``min_win_rate``.

    """



    __tablename__ = "partner_tier_eligibility_rules"



    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tier_id = Column(

        Uuid(as_uuid=True),

        ForeignKey("partner_tiers.id"),

        nullable=False,

    )

    rule_type = Column(String, nullable=False)

    rule_value = Column(String, nullable=False)

    description = Column(String, nullable=True)



    tier = relationship("PartnerTierConfig", back_populates="eligibility_rules")





class ActivationChecklistConfig(Base):

    """Sprint 13 / FPRM-213 — admin-configurable activation criteria.



    Rows can scope a criterion to a specific partner category code, a specific

    tier name, both, or neither (NULL on both columns = applies to every

    partner). Migration 022 seeds the six criteria that ``activation.py``

    currently enforces in hard-coded form. Dynamic enforcement that reads

    these rows is deferred to Phase 5.

    """



    __tablename__ = "activation_checklist_config"



    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    partner_category_code = Column(String, nullable=True)

    tier_name = Column(String, nullable=True)

    criterion_key = Column(String, nullable=False)

    is_required = Column(Boolean, default=True, nullable=False)

    description = Column(String, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)



# ============================================================
# Sprint 15 / FPRM-239 — Quoting module data model
# ============================================================
#
# Pricing catalogue (migration 023): FeaturePlanPrice, VolumeDiscountTier,
# AddonCatalogItem hold the live Fracttal pricing rules. They are seeded
# from the Fracttal Pricing and Quotation Specification.
#
# Quote schema (migration 024): Quote (header), QuoteVersion (one snapshot
# per pricing iteration / scenario), QuoteLineItem (computed line items).
# Every Quote is bound to a deal_registrations row; quote_engine.calculate_quote
# is the single source of truth for line-item generation (AD-16).


class FeaturePlanPrice(Base):
    """Sprint 15 / FPRM-239. Per-plan annual list prices for the Fracttal CMMS.

    Three rows (Starter, Professional, Enterprise) are seeded by migration 023
    from the Fracttal Pricing and Quotation Specification. ``effective_from``
    lets future price updates coexist without losing historical pricing.
    """

    __tablename__ = "feature_plan_prices"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_code = Column(String, nullable=False)          # "starter"|"professional"|"enterprise"
    feature_pack_annual = Column(Numeric(10, 2), nullable=False)
    transactional_user_annual = Column(Numeric(10, 2), nullable=False)
    limited_tech_user_annual = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    effective_from = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class VolumeDiscountTier(Base):
    """Sprint 15 / FPRM-239. Volume discount bands applied per user count tier.

    Six rows seeded by migration 023 covering 1-10 / 11-50 / 51-100 / 101-300 /
    301-500 / 500+ users. The unbounded top band sets ``max_users=NULL``.
    Discounts apply only to Transactional and Limited Technician users; the
    Feature Pack always sits in the 0% column.
    """

    __tablename__ = "volume_discount_tiers"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    min_users = Column(Integer, nullable=False)
    max_users = Column(Integer, nullable=True)          # null = no upper bound
    transactional_user_discount_pct = Column(Numeric(5, 2), nullable=False)
    limited_tech_user_discount_pct = Column(Numeric(5, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class AddonCatalogItem(Base):
    """Sprint 15 / FPRM-239. Catalogue of add-ons selectable for Starter /
    Professional plans (Enterprise includes everything by default).

    Twenty-one rows seeded by migration 023 matching the add-on catalogue in
    the Fracttal Pricing and Quotation Specification. ``available_starter`` and
    ``available_professional`` gate per-plan visibility in the quote form;
    ``included_enterprise`` is always True (Enterprise always includes all
    add-ons at no extra charge).
    """

    __tablename__ = "addon_catalog_items"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    addon_key = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    monthly_price = Column(Numeric(10, 2), nullable=False)
    available_starter = Column(Boolean, default=False, nullable=False)
    available_professional = Column(Boolean, default=False, nullable=False)
    included_enterprise = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # Sprint 20 / FPRM-318 -- catalogue organisation. Both are admin-maintainable
    # via PATCH /internal/config/pricing/addons/{id} (AD-25); migration 028 only
    # creates the columns -- the categorisation taxonomy is data, not code.
    category = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")


class Quote(Base):
    """Sprint 15 / FPRM-239. Quote header bound to a registered deal.

    A quote can have multiple versions (channel manager iterating on pricing)
    and multiple scenarios per version (Good / Better / Best comparison).
    ``active_version`` and ``active_scenario`` track the currently selected
    pricing line that should be shown to the partner and printed on the PDF
    (Sprint 16). ``currency_code`` is display-only; FX conversion is out of
    Phase 5 scope.
    """

    __tablename__ = "quotes"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id = Column(Uuid(as_uuid=True), ForeignKey("deal_registrations.id"), nullable=False)
    partner_org_id = Column(Uuid(as_uuid=True), ForeignKey("partner_organizations.id"), nullable=False)
    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    quote_name = Column(String, nullable=True)
    currency_code = Column(String(3), default="USD", nullable=False)
    active_version = Column(Integer, default=1, nullable=False)
    active_scenario = Column(String, nullable=True)
    status = Column(String, default="draft", nullable=False)  # draft|sent|accepted|expired
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_quotes_deal_id", "deal_id"),
    )


class QuoteVersion(Base):
    """Sprint 15 / FPRM-239. Versioned snapshot of pricing inputs + computed
    totals for a Quote.

    Each version captures the channel manager's pricing iteration: plan,
    discount %, user quantities, add-ons. ``selected_addons`` is a JSON list
    of ``addon_key`` strings. ``grand_total_*`` is computed by
    ``quote_engine.calculate_quote`` and persisted here so list views do not
    need to recompute on every read. ``pdf_artifact_path`` is populated in
    Sprint 16 when a customer-facing PDF is generated.

    Soft-deleted via ``is_deleted``; the active version cannot be deleted.
    """

    __tablename__ = "quote_versions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id = Column(Uuid(as_uuid=True), ForeignKey("quotes.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    scenario_label = Column(String, nullable=True)        # "good"|"better"|"best"|null
    feature_plan = Column(String, nullable=False)          # starter|professional|enterprise
    feature_plan_discount_pct = Column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    qty_transactional_users = Column(Integer, nullable=False)
    qty_limited_tech_users = Column(Integer, nullable=False)
    selected_addons = Column(JSON, default=list, nullable=False)
    grand_total_before_discount = Column(Numeric(12, 2), nullable=False)
    grand_total_after_discount = Column(Numeric(12, 2), nullable=False)
    pdf_artifact_path = Column(String, nullable=True)
    pdf_artifact_data = Column(Text, nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)
    pdf_filename = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("quote_id", "version_number", name="uq_quote_versions_quote_version"),
        Index("ix_quote_versions_quote_id", "quote_id"),
    )


class QuoteLineItem(Base):
    """Sprint 15 / FPRM-239. Individual quote line items computed by
    ``quote_engine.calculate_quote``.

    ``line_type`` values: ``feature_pack`` | ``transactional_user`` |
    ``limited_tech_user`` | ``addon`` | ``free_allocation``. Multiple lines of
    the same type may exist when volume discount bands split a user quantity
    across tiers (e.g. 25 Limited Tech users -> 10 at 0%, 15 at 30%).
    ``addon_key`` is set only when ``line_type == 'addon'``.
    """

    __tablename__ = "quote_line_items"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_version_id = Column(
        Uuid(as_uuid=True), ForeignKey("quote_versions.id"), nullable=False
    )
    line_order = Column(Integer, nullable=False)
    line_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount_pct = Column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    total_before_discount = Column(Numeric(12, 2), nullable=False)
    total_after_discount = Column(Numeric(12, 2), nullable=False)
    addon_key = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_quote_line_items_version_id", "quote_version_id"),
    )
