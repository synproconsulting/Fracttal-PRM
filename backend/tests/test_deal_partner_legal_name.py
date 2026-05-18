"""Tests for partner_legal_name in deal serialiser (Sprint 9 / FPRM-143).

Internal queue + single-deal endpoints must surface the partner org's legal
name instead of forcing reviewers to read truncated UUIDs.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    DealRegistration,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_deal_partner_legal_name.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_deal_partner_legal_name.db"):
        try: os.remove("./test_deal_partner_legal_name.db")
        except OSError: pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try: yield db
    finally: db.close()


def _make_user(role, partner_org_id=None):
    return User(id=uuid.uuid4(), email=f"{role.value}-{uuid.uuid4().hex[:6]}@t.com",
                hashed_password="x", role=role.value, partner_org_id=partner_org_id, is_active=True)


def _make_org(db, legal_name="Acme Inc"):
    o = PartnerOrganization(id=uuid.uuid4(), legal_name=legal_name,
                            program_type=ProgramType.distributor,
                            partner_category=PartnerCategory.reseller,
                            status=PartnerStatus.active)
    db.add(o); db.commit(); db.refresh(o)
    return o


def _make_deal(db, org_id, status="submitted"):
    d = DealRegistration(id=uuid.uuid4(), partner_org_id=org_id, status=status,
                         customer_name="ACME Corp", deal_name="Deal Z")
    db.add(d); db.commit(); db.refresh(d)
    return d


def _override(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_internal_list_includes_partner_legal_name(db_session):
    org = _make_org(db_session, legal_name="Specific Legal Name Corp")
    _make_deal(db_session, org.id)
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = _override(db_session, reviewer)
    r = client.get("/internal/deals?status=submitted")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    matched = [x for x in items if x.get("partner_legal_name") == "Specific Legal Name Corp"]
    assert matched, f"partner_legal_name missing or wrong: {[x.get('partner_legal_name') for x in items]}"


def test_get_deal_includes_partner_legal_name_internal(db_session):
    org = _make_org(db_session, legal_name="Detail Page Corp")
    deal = _make_deal(db_session, org.id)
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = _override(db_session, reviewer)
    r = client.get(f"/deal-registrations/{deal.id}")
    assert r.status_code == 200
    assert r.json()["partner_legal_name"] == "Detail Page Corp"


def test_get_deal_includes_partner_legal_name_partner(db_session):
    """Partner side also receives the field (own org only — not leaky)."""
    org = _make_org(db_session, legal_name="Partner Own Corp")
    deal = _make_deal(db_session, org.id)
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = _override(db_session, partner)
    r = client.get(f"/deal-registrations/{deal.id}")
    assert r.status_code == 200
    assert r.json()["partner_legal_name"] == "Partner Own Corp"
