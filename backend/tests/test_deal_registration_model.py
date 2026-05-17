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
