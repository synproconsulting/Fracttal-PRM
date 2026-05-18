"""Tests for backend/conflict_checker.py and the override-conflict endpoint (Sprint 10 / FPRM-157)."""
import os
import sys
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    DealRegistration,
    PartnerActivationChecklist,
    PartnerOrganization,
    User,
)
from roles import UserRole
from conflict_checker import check_deal_conflict


@pytest.fixture()
def db_session():
    """Function-scoped in-memory SQLite — conflict tests query across rows so
    state bleed between tests would mask logic bugs. ``StaticPool`` keeps all
    connections pointing at the same in-memory DB so TestClient (which opens
    its own session) sees data committed by the fixture."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _make_partner(db, name="Partner Co"):
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=name,
        program_type="distributor",
        partner_category="reseller",
        status="active",
        monthly_fee_status="current",
        contract_start_date=date(2026, 1, 1),
    )
    db.add(org)
    # Activation row so deal-registration endpoints don't 412 in endpoint tests
    db.add(
        PartnerActivationChecklist(
            id=uuid.uuid4(),
            partner_org_id=org.id,
            profile_complete=True,
            documents_uploaded=True,
            terms_signed=True,
            baseline_training_complete=True,
            activation_complete=True,
            activated_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, role: UserRole, partner_org_id=None):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_deal(db, partner_org_id, *, status="submitted", domain="acme.com", name="Acme Deal"):
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status=status,
        customer_name="Acme",
        customer_domain=domain,
        deal_name=name,
        conflict_status="not_checked",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def _override(db_session, user):
    def _db():
        yield db_session
    def _u():
        return user
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _u


# ---- check_deal_conflict unit tests ----


def test_no_existing_deals_returns_clear(db_session):
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, status="submitted")
    result = check_deal_conflict(db_session, deal.id)
    assert result.conflict_status == "clear"
    assert result.conflicting_deal_ids == []


def test_same_partner_same_domain_is_clear(db_session):
    partner = _make_partner(db_session, "Same Partner")
    deal_one = _make_deal(db_session, partner.id, status="submitted", name="Deal 1")
    _make_deal(db_session, partner.id, status="submitted", name="Deal 2")
    result = check_deal_conflict(db_session, deal_one.id)
    assert result.conflict_status == "clear"


def test_different_partner_active_deal_is_conflict(db_session):
    partner_a = _make_partner(db_session, "Partner A")
    partner_b = _make_partner(db_session, "Partner B")
    _make_deal(db_session, partner_a.id, status="submitted", name="A's Deal")
    deal_b = _make_deal(db_session, partner_b.id, status="submitted", name="B's Deal")
    result = check_deal_conflict(db_session, deal_b.id)
    assert result.conflict_status == "conflict_detected"
    assert len(result.conflicting_deal_ids) == 1


def test_different_partner_rejected_deal_is_clear(db_session):
    partner_a = _make_partner(db_session, "Partner A")
    partner_b = _make_partner(db_session, "Partner B")
    _make_deal(db_session, partner_a.id, status="rejected", name="A's rejected")
    deal_b = _make_deal(db_session, partner_b.id, status="submitted", name="B's Deal")
    result = check_deal_conflict(db_session, deal_b.id)
    assert result.conflict_status == "clear"


def test_null_customer_domain_is_not_checked(db_session):
    partner = _make_partner(db_session)
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        status="submitted",
        customer_name="Acme",
        customer_domain=None,
        deal_name="No Domain Deal",
        conflict_status="not_checked",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)
    result = check_deal_conflict(db_session, deal.id)
    assert result.conflict_status == "not_checked"
    assert "No customer domain" in result.notes


def test_empty_string_customer_domain_is_not_checked(db_session):
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, domain="")
    result = check_deal_conflict(db_session, deal.id)
    assert result.conflict_status == "not_checked"


def test_under_review_counts_as_active(db_session):
    partner_a = _make_partner(db_session, "A")
    partner_b = _make_partner(db_session, "B")
    _make_deal(db_session, partner_a.id, status="under_review")
    deal_b = _make_deal(db_session, partner_b.id, status="submitted", name="B")
    result = check_deal_conflict(db_session, deal_b.id)
    assert result.conflict_status == "conflict_detected"


def test_approved_counts_as_active(db_session):
    partner_a = _make_partner(db_session, "A")
    partner_b = _make_partner(db_session, "B")
    _make_deal(db_session, partner_a.id, status="approved")
    deal_b = _make_deal(db_session, partner_b.id, status="submitted", name="B")
    result = check_deal_conflict(db_session, deal_b.id)
    assert result.conflict_status == "conflict_detected"


# ---- override-conflict endpoint tests ----


def test_override_conflict_sets_status_clear(db_session):
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, status="under_review")
    deal.conflict_status = "conflict_detected"
    deal.conflict_notes = "Conflict detected with 1 deal"
    db_session.commit()

    cm = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.post(
            f"/internal/deals/{deal.id}/override-conflict",
            json={"override_notes": "Customers confirmed it's a parent/subsidiary case."},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["conflict_status"] == "clear"
    assert "[OVERRIDE by" in body["conflict_notes"]


def test_override_conflict_requires_override_notes(db_session):
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, status="under_review")
    sa = _make_user(db_session, UserRole.system_admin)
    _override(db_session, sa)
    try:
        client = TestClient(app)
        r = client.post(
            f"/internal/deals/{deal.id}/override-conflict",
            json={"override_notes": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422


def test_override_conflict_forbidden_for_partner_admin(db_session):
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, status="under_review")
    pa = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, pa)
    try:
        client = TestClient(app)
        r = client.post(
            f"/internal/deals/{deal.id}/override-conflict",
            json={"override_notes": "trying"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


def test_override_conflict_forbidden_for_channel_ops_admin(db_session):
    """FPRM-157: channel_ops_admin is explicitly excluded from OVERRIDE_ROLES."""
    partner = _make_partner(db_session)
    deal = _make_deal(db_session, partner.id, status="under_review")
    user = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/internal/deals/{deal.id}/override-conflict",
            json={"override_notes": "trying"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


# ---- submit-wires-conflict-check integration test ----


def test_submit_records_clear_conflict_status_when_no_other_deals(db_session):
    partner = _make_partner(db_session)
    pa = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, pa)
    try:
        client = TestClient(app)
        # Create draft, then submit
        r = client.post(
            "/deal-registrations",
            json={
                "customer_name": "Acme",
                "customer_domain": "uniqueacme.com",
                "deal_name": "Acme Deal",
            },
        )
        assert r.status_code == 201, r.text
        deal_id = r.json()["id"]
        r = client.post(f"/deal-registrations/{deal_id}/submit")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["conflict_status"] == "clear"
    assert body["conflict_checked_at"] is not None


def test_submit_records_conflict_detected_when_other_partner_active(db_session):
    partner_a = _make_partner(db_session, "Partner A")
    partner_b = _make_partner(db_session, "Partner B")
    # partner_a has an active deal on the same domain
    _make_deal(db_session, partner_a.id, status="submitted", domain="hotdomain.com", name="A's lock")

    pb = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner_b.id)
    _override(db_session, pb)
    try:
        client = TestClient(app)
        r = client.post(
            "/deal-registrations",
            json={
                "customer_name": "Acme",
                "customer_domain": "hotdomain.com",
                "deal_name": "B's attempt",
            },
        )
        assert r.status_code == 201
        deal_id = r.json()["id"]
        r = client.post(f"/deal-registrations/{deal_id}/submit")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["conflict_status"] == "conflict_detected"
    assert "hotdomain.com" in (body["conflict_notes"] or "")
