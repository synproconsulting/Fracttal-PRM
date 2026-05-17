"""Tests for partner_profiles router (FPRM-106 / Sprint 7)."""
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
import models  # noqa: F401  registers all models
from models import AuditLog, PartnerOrganization, PartnerProfile, User
from roles import UserRole
from routers.partner_profiles_router import calculate_profile_completeness


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_partner_profiles.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_partner_profiles.db"):
        try:
            os.remove("./test_partner_profiles.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_partner(db, legal_name="Acme Corp"):
    partner = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type="distributor",
        partner_category="master",
        status="active",
        monthly_fee_status="current",
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def _make_profile(db, partner_org_id, **kwargs):
    defaults = {"id": uuid.uuid4(), "partner_org_id": partner_org_id, "profile_completeness_pct": 0}
    defaults.update(kwargs)
    profile = PartnerProfile(**defaults)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


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


def _override(db_session, user):
    def _db_dep():
        yield db_session

    def _user_dep():
        return user

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = _user_dep


def _clear():
    app.dependency_overrides.clear()


def test_calculate_profile_completeness_empty_profile():
    profile = PartnerProfile(partner_org_id=uuid.uuid4())
    assert calculate_profile_completeness(profile) == 0


def test_calculate_profile_completeness_partial_profile():
    profile = PartnerProfile(
        partner_org_id=uuid.uuid4(),
        year_established=2020,
        employee_count=15,
        annual_revenue="1M-5M",
    )
    assert calculate_profile_completeness(profile) == round(3 / 11 * 100)


def test_calculate_profile_completeness_full_profile():
    profile = PartnerProfile(
        partner_org_id=uuid.uuid4(),
        year_established=2020,
        employee_count=15,
        annual_revenue="1M-5M",
        shareholders=[{"name": "Alice", "pct": 100}],
        other_software_products="ERP X",
        cmms_experience=True,
        sales_marketing_strategy="Inbound + outbound",
        technical_support_team=True,
        implementation_services=True,
        partnership_goals="Grow LATAM",
        market_growth_plan="3-year plan",
    )
    assert calculate_profile_completeness(profile) == 100


def test_get_partner_profile_as_partner_admin_own_org(db_session):
    partner = _make_partner(db_session, "Own Org")
    _make_profile(db_session, partner.id, year_established=2018, employee_count=22, profile_completeness_pct=18)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partner-profiles/{partner.id}")
    finally:
        _clear()
    assert r.status_code == 200
    data = r.json()
    assert data["year_established"] == 2018
    assert data["employee_count"] == 22
    assert data["profile_completeness_pct"] == 18


def test_get_partner_profile_other_org_denied(db_session):
    partner_a = _make_partner(db_session, "A Co")
    partner_b = _make_partner(db_session, "B Co")
    _make_profile(db_session, partner_b.id)
    user_a = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner_a.id)
    _override(db_session, user_a)
    try:
        client = TestClient(app)
        r = client.get(f"/partner-profiles/{partner_b.id}")
    finally:
        _clear()
    assert r.status_code == 403


def test_get_partner_profile_internal_can_see_any(db_session):
    partner = _make_partner(db_session, "Internal View Co")
    _make_profile(db_session, partner.id, employee_count=100)
    user = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partner-profiles/{partner.id}")
    finally:
        _clear()
    assert r.status_code == 200
    assert r.json()["employee_count"] == 100


def test_get_partner_profile_not_found(db_session):
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partner-profiles/{uuid.uuid4()}")
    finally:
        _clear()
    assert r.status_code == 404


def test_patch_partner_profile_updates_fields(db_session):
    partner = _make_partner(db_session, "Update Fields Co")
    _make_profile(db_session, partner.id)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partner-profiles/{partner.id}",
            json={
                "year_established": 2015,
                "employee_count": 42,
                "annual_revenue": "10M-50M",
                "partnership_goals": "Become master partner in LATAM",
            },
        )
    finally:
        _clear()
    assert r.status_code == 200
    data = r.json()
    assert data["year_established"] == 2015
    assert data["employee_count"] == 42
    assert data["annual_revenue"] == "10M-50M"
    assert data["partnership_goals"] == "Become master partner in LATAM"


def test_patch_partner_profile_recalculates_completeness(db_session):
    partner = _make_partner(db_session, "Completeness Co")
    _make_profile(db_session, partner.id)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partner-profiles/{partner.id}",
            json={
                "year_established": 2020,
                "employee_count": 30,
                "annual_revenue": "5M-10M",
                "shareholders": [{"name": "Bob", "pct": 100}],
                "other_software_products": "None",
                "cmms_experience": False,
                "sales_marketing_strategy": "Outbound",
                "technical_support_team": True,
                "implementation_services": False,
                "partnership_goals": "Grow",
                "market_growth_plan": "Plan",
            },
        )
    finally:
        _clear()
    assert r.status_code == 200
    assert r.json()["profile_completeness_pct"] == 100


def test_patch_partner_profile_forbidden_for_other_org(db_session):
    partner_a = _make_partner(db_session, "A Org")
    partner_b = _make_partner(db_session, "B Org")
    _make_profile(db_session, partner_b.id)
    user_a = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner_a.id)
    _override(db_session, user_a)
    try:
        client = TestClient(app)
        r = client.patch(f"/partner-profiles/{partner_b.id}", json={"employee_count": 99})
    finally:
        _clear()
    assert r.status_code == 403


def test_patch_partner_profile_partner_user_role_denied(db_session):
    partner = _make_partner(db_session, "Read Only Co")
    _make_profile(db_session, partner.id)
    user = _make_user(db_session, UserRole.partner_user, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(f"/partner-profiles/{partner.id}", json={"employee_count": 1})
    finally:
        _clear()
    assert r.status_code == 403


def test_patch_partner_profile_logs_audit_event(db_session):
    partner = _make_partner(db_session, "Audited Profile Co")
    _make_profile(db_session, partner.id)
    user = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(f"/partner-profiles/{partner.id}", json={"employee_count": 7})
    finally:
        _clear()
    assert r.status_code == 200
    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "partner_profile.update")
        .all()
    )
    assert len(entries) >= 1
    assert entries[-1].after_state["employee_count"] == 7


def test_patch_partner_profile_ignores_unknown_fields(db_session):
    partner = _make_partner(db_session, "Unknown Fields Co")
    _make_profile(db_session, partner.id)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partner-profiles/{partner.id}",
            json={"employee_count": 5, "id": uuid.uuid4().hex, "profile_completeness_pct": 999},
        )
    finally:
        _clear()
    assert r.status_code == 200
    data = r.json()
    assert data["employee_count"] == 5
    assert data["profile_completeness_pct"] != 999  # recomputed, not stuffed
