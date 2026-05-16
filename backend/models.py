import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
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
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
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


class PartnerDocument(Base):
    __tablename__ = "partner_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_org_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("partner_organizations.id"),
        nullable=False,
    )
    document_type = Column(SAEnum(DocumentType, name="document_type"), nullable=False)
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
