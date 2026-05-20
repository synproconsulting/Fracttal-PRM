"""Tests for the DealRegistration model (Sprint 8 / FPRM-125)."""
import os
import sys
import uuid
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database import Base
import models  # noqa: F401
from models import (
    DealRegistration,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
)


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_deal_registration_model.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_deal_registration_model.db"):
        try:
            os.remove("./test_deal_registration_model.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def make_partner_org(db) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Deal Corp {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def test_create_deal_with_required_fields_persists(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Acme Corp",
        deal_name="Acme — CMMS rollout",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)

    assert deal.id is not None
    assert deal.partner_org_id == org.id
    assert deal.customer_name == "Acme Corp"
    assert deal.deal_name == "Acme — CMMS rollout"


def test_status_defaults_to_draft(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Customer One",
        deal_name="Deal One",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.status == "draft"


def test_conflict_status_defaults_to_not_checked(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Customer Two",
        deal_name="Deal Two",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.conflict_status == "not_checked"


def test_fk_to_partner_organizations_enforced(db_session):
    """Inserting a deal with a partner_org_id that does not exist must fail.

    sqlite enforces FK constraints only when ``PRAGMA foreign_keys = ON``;
    the default test engine does not enable this, so we instead exercise the
    SQL-level constraint by enabling it on the connection.
    """
    db_session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys = ON"))
    bad_id = uuid.uuid4()
    deal = DealRegistration(
        partner_org_id=bad_id,
        customer_name="Ghost Customer",
        deal_name="Ghost Deal",
    )
    db_session.add(deal)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_nullable_optional_fields_accept_none(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Optional Customer",
        deal_name="Optional Deal",
        customer_domain=None,
        customer_contact_email=None,
        estimated_deal_value=None,
        commission_structure_id=None,
        commission_rate_snapshot=None,
        deal_notes=None,
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.customer_domain is None
    assert deal.commission_structure_id is None
    assert deal.commission_rate_snapshot is None


def test_commission_snapshot_persists_numeric_value(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Snapshot Customer",
        deal_name="Snapshot Deal",
        commission_rate_snapshot=18.5,
        commission_type="reseller",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.commission_rate_snapshot == pytest.approx(18.5)
    assert deal.commission_type == "reseller"


def test_estimated_deal_value_and_close_date_persist(db_session):
    org = make_partner_org(db_session)
    close = date.today() + timedelta(days=45)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Value Customer",
        deal_name="Value Deal",
        estimated_deal_value=125000.0,
        estimated_close_date=close,
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.estimated_deal_value == pytest.approx(125000.0)
    assert deal.estimated_close_date == close


def test_timestamps_populate_on_create_and_update(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Time Customer",
        deal_name="Time Deal",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert isinstance(deal.created_at, datetime)
    first_updated = deal.updated_at
    assert isinstance(first_updated, datetime)

    deal.customer_name = "Time Customer — renamed"
    db_session.commit()
    db_session.refresh(deal)
    assert deal.updated_at >= first_updated


# ---- Sprint 20 / FPRM-315 -- Section A + Section B SPICED schema extension


def test_section_a_additional_fields_persist(db_session):
    org = make_partner_org(db_session)
    eng = date.today()
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Section A Customer",
        deal_name="Section A Deal",
        engagement_date=eng,
        prospect_phone="+27 11 555 0123",
        compiled_by="Johan W.",
        prospect_contact_name="Alex Smith",
        prospect_contact_position="Maintenance Manager",
        prospect_website="https://example.com",
        industry_sector="Manufacturing",
        company_size="51-200",
        feature_plan_preference="professional",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.engagement_date == eng
    assert deal.prospect_phone == "+27 11 555 0123"
    assert deal.compiled_by == "Johan W."
    assert deal.prospect_contact_name == "Alex Smith"
    assert deal.prospect_contact_position == "Maintenance Manager"
    assert deal.prospect_website == "https://example.com"
    assert deal.industry_sector == "Manufacturing"
    assert deal.company_size == "51-200"
    assert deal.feature_plan_preference == "professional"


def test_section_b_current_systems_persist(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Section B Systems Customer",
        deal_name="Section B Systems Deal",
        current_system="excel",
        old_system="paper",
        inventory_stores="cmms",
        work_orders_prs="excel",
        monitoring_system="none",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.current_system == "excel"
    assert deal.old_system == "paper"
    assert deal.inventory_stores == "cmms"
    assert deal.work_orders_prs == "excel"
    assert deal.monitoring_system == "none"


def test_section_b_feature_requirements_persist(db_session):
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Features Customer",
        deal_name="Features Deal",
        need_asset_depreciation=True,
        need_wo_wr=True,
        need_reports=True,
        need_tool_management=False,
        need_purchasing=None,
        need_integration=True,
        integration_with="SAP, Power BI",
        need_multi_language=True,
        languages_required="English, Spanish",
        need_asset_management=True,
        need_document_management=False,
        need_cost_tracking=True,
        need_monitoring=False,
        need_schedule_third_parties=True,
        need_track_labour=True,
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.need_asset_depreciation is True
    assert deal.need_tool_management is False
    assert deal.need_purchasing is None
    assert deal.integration_with == "SAP, Power BI"
    assert deal.languages_required == "English, Spanish"
    assert deal.need_track_labour is True


def test_section_b_spiced_narratives_persist(db_session):
    org = make_partner_org(db_session)
    long_text = "Client struggles with " + ("manual coordination, " * 20).strip(", ")
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="SPICED Customer",
        deal_name="SPICED Deal",
        about_client="Mid-size manufacturer with 3 plants.",
        pain=long_text,
        impact="Lost production time, frustrated technicians.",
        critical_event="Existing CMMS licence renewal due 2026-09-30.",
        decision="CTO + Head of Operations; target sign-off Q3.",
        next_steps="Demo next week; quote within 10 days.",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.about_client == "Mid-size manufacturer with 3 plants."
    assert deal.pain == long_text  # Text column preserves long strings
    assert "renewal due 2026-09-30" in deal.critical_event
    assert deal.next_steps.startswith("Demo next week")


def test_section_b_fields_default_to_null_when_omitted(db_session):
    """No-regression: creating a deal without any Section A/B fields leaves
    them all null (or False for created_on_behalf_of). Pre-existing partner
    deals must continue to work without supplying the new fields.
    """
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="Bare Customer",
        deal_name="Bare Deal",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    # Section A
    assert deal.engagement_date is None
    assert deal.prospect_phone is None
    assert deal.feature_plan_preference is None
    # Section B current systems
    assert deal.current_system is None
    assert deal.monitoring_system is None
    # Section B feature requirements
    assert deal.need_asset_depreciation is None
    assert deal.integration_with is None
    # Section B SPICED
    assert deal.about_client is None
    assert deal.pain is None
    # FPRM-317 -- internal-creation flag defaults to False (not null)
    assert deal.created_on_behalf_of is False


def test_created_on_behalf_of_set_true_persists(db_session):
    """FPRM-317 -- when an internal user creates a deal on behalf of a
    partner, the flag is True and is read back correctly.
    """
    org = make_partner_org(db_session)
    deal = DealRegistration(
        partner_org_id=org.id,
        customer_name="On Behalf Customer",
        deal_name="On Behalf Deal",
        created_on_behalf_of=True,
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    assert deal.created_on_behalf_of is True


def test_extended_schema_columns_present_via_inspector(test_engine):
    """Smoke test: the table actually has the columns Sprint 20 / FPRM-315
    promised. Catches a missing model field before any API test does.
    """
    from sqlalchemy import inspect as sa_inspect
    cols = {c["name"] for c in sa_inspect(test_engine).get_columns("deal_registrations")}
    expected = {
        # Section A
        "engagement_date", "prospect_phone", "compiled_by",
        "prospect_contact_name", "prospect_contact_position",
        "prospect_website", "industry_sector", "company_size",
        "feature_plan_preference",
        # Section B current systems
        "current_system", "old_system", "inventory_stores",
        "work_orders_prs", "monitoring_system",
        # Section B feature requirements (sample)
        "need_asset_depreciation", "need_integration", "integration_with",
        "need_multi_language", "languages_required", "need_track_labour",
        # Section B SPICED
        "about_client", "pain", "impact", "critical_event",
        "decision", "next_steps",
        # FPRM-317
        "created_on_behalf_of",
    }
    missing = expected - cols
    assert not missing, f"Missing columns on deal_registrations: {missing}"
