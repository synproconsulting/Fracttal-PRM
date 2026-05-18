"""Tests for GET /partners/{id}/commission-rates (Sprint 10 / FPRM-158)."""
import os
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401  registers all models
from models import (
    CommissionStructure,
    CommissionYear,
    PartnerCategoryConfig,
    PartnerOrganization,
    User,
)
from roles import UserRole


@pytest.fixture()
def db_session():
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


def _make_partner(db, category="reseller"):
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"{category.title()} Co",
        program_type="distributor",
        partner_category=category,
        status="active",
        monthly_fee_status="current",
    )
    db.add(org)
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


def _seed_commission_rows(db, category_code="reseller"):
    """Seed the category config + a handful of commission_structures rows."""
    # The migration normally seeds these; the in-memory test DB starts empty.
    cfg = PartnerCategoryConfig(
        id=uuid.uuid4(),
        code=category_code,
        display_name=category_code.title(),
        deal_reg_sla_hours=96,
        max_discount_pct=Decimal("20.0"),
        monthly_fee_usd=Decimal("200.0"),
        is_active=True,
    )
    db.add(cfg)
    rows = [
        CommissionStructure(
            id=uuid.uuid4(),
            partner_category_code=category_code,
            commission_type="autonomous_sell",
            year=CommissionYear.year_1,
            commission_pct=Decimal("50.0"),
            subpartner_uplift_pct=Decimal("10.0"),
            applies_to_upsell=True,
            notes="Test",
        ),
        CommissionStructure(
            id=uuid.uuid4(),
            partner_category_code=category_code,
            commission_type="autonomous_sell",
            year=CommissionYear.year_2_plus,
            commission_pct=Decimal("30.0"),
            subpartner_uplift_pct=Decimal("10.0"),
            applies_to_upsell=True,
        ),
        CommissionStructure(
            id=uuid.uuid4(),
            partner_category_code=category_code,
            commission_type="indirect_sell",
            year=CommissionYear.year_1,
            commission_pct=Decimal("30.0"),
            subpartner_uplift_pct=Decimal("10.0"),
            applies_to_upsell=True,
        ),
    ]
    for r in rows:
        db.add(r)
    db.commit()


def _override(db_session, user):
    def _db():
        yield db_session
    def _u():
        return user
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _u


def test_partner_admin_can_read_own_commission_rates(db_session):
    partner = _make_partner(db_session, "reseller")
    _seed_commission_rows(db_session, "reseller")
    pa = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, pa)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["partner_category_code"] == "reseller"
    assert len(body["items"]) == 3
    types = {item["commission_type"] for item in body["items"]}
    assert "autonomous_sell" in types
    # year_1 autonomous_sell should be 50%
    y1 = [i for i in body["items"] if i["commission_type"] == "autonomous_sell" and i["year"] == "year_1"][0]
    assert y1["percentage"] == 50.0


def test_partner_admin_other_org_forbidden(db_session):
    partner_a = _make_partner(db_session, "reseller")
    partner_b = _make_partner(db_session, "master")
    _seed_commission_rows(db_session, "master")
    pa = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner_a.id)
    _override(db_session, pa)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner_b.id}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


def test_channel_manager_can_read_any_partner(db_session):
    partner = _make_partner(db_session, "master")
    _seed_commission_rows(db_session, "master")
    cm = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["partner_category_code"] == "master"


def test_system_admin_can_read_any_partner(db_session):
    partner = _make_partner(db_session, "promotor")
    _seed_commission_rows(db_session, "promotor")
    sa = _make_user(db_session, UserRole.system_admin)
    _override(db_session, sa)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["partner_category_code"] == "promotor"


def test_404_for_unknown_partner(db_session):
    sa = _make_user(db_session, UserRole.system_admin)
    _override(db_session, sa)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{uuid.uuid4()}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


def test_empty_items_when_no_rows_seeded(db_session):
    partner = _make_partner(db_session, "reseller")
    sa = _make_user(db_session, UserRole.system_admin)
    _override(db_session, sa)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/commission-rates")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["items"] == []
