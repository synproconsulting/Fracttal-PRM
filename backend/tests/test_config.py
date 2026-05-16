"""Tests for partner category + commission config router (FPRM-58)."""
import os
import sys
import uuid
from decimal import Decimal

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
    CommissionStructure,
    CommissionType,
    CommissionYear,
    PartnerCategoryConfig,
    User,
)
from roles import UserRole


SEED_CATEGORIES = [
    ("master", "Master Partner", 48, 40),
    ("promotor", "Promotor Partner", 72, 30),
    ("reseller", "Reseller Partner", 96, 20),
]


SEED_COMMISSIONS = [
    # (type, year_1_pct, year_2_plus_pct, uplift_y1)
    ("autonomous_sell", 50.0, 30.0, 10.0),
    ("indirect_sell", 30.0, 30.0, 10.0),
    ("direct_sell", 10.0, 10.0, 0.0),
    ("co_sell_shared", 25.0, 25.0, 10.0),
]


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_config.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Manually seed: Base.metadata.create_all does not run alembic data migrations
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    for code, name, sla, max_disc in SEED_CATEGORIES:
        cat = PartnerCategoryConfig(
            id=uuid.uuid4(),
            code=code,
            display_name=name,
            deal_reg_sla_hours=sla,
            max_discount_pct=Decimal(str(max_disc)),
            monthly_fee_usd=Decimal("200"),
            is_active=True,
        )
        db.add(cat)
    db.flush()
    for code, _, _, _ in SEED_CATEGORIES:
        for ctype, y1, y2, uplift in SEED_COMMISSIONS:
            db.add(CommissionStructure(
                id=uuid.uuid4(),
                partner_category_code=code,
                commission_type=ctype,
                year="year_1",
                commission_pct=Decimal(str(y1)),
                subpartner_uplift_pct=Decimal(str(uplift)),
                applies_to_upsell=True,
            ))
            db.add(CommissionStructure(
                id=uuid.uuid4(),
                partner_category_code=code,
                commission_type=ctype,
                year="year_2_plus",
                commission_pct=Decimal(str(y2)),
                subpartner_uplift_pct=Decimal("0"),
                applies_to_upsell=True,
            ))
    db.commit()
    db.close()

    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_config.db"):
        try:
            os.remove("./test_config.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user(role, partner_org_id=None):
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@t.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def override(db, user):
    def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user


def override_db_only(db):
    def _db():
        yield db
    app.dependency_overrides[get_db] = _db


def clear():
    app.dependency_overrides.clear()


def test_partner_categories_public_endpoint(db_session):
    """GET /config/partner-categories must work without auth."""
    override_db_only(db_session)
    try:
        client = TestClient(app)
        r = client.get("/config/partner-categories")
    finally:
        clear()
    assert r.status_code == 200
    codes = [c["code"] for c in r.json()["items"]]
    assert "master" in codes
    assert "promotor" in codes
    assert "reseller" in codes


def test_seed_categories_have_correct_sla(db_session):
    cats = {c.code: c for c in db_session.query(PartnerCategoryConfig).all()}
    assert int(cats["master"].deal_reg_sla_hours) == 48
    assert int(cats["promotor"].deal_reg_sla_hours) == 72
    assert int(cats["reseller"].deal_reg_sla_hours) == 96


def test_commission_lookup_autonomous_y1(db_session):
    """autonomous_sell year_1 must be 50% per Distributor Agreement."""
    row = (
        db_session.query(CommissionStructure)
        .filter(
            CommissionStructure.partner_category_code == "master",
            CommissionStructure.commission_type == CommissionType.autonomous_sell,
            CommissionStructure.year == CommissionYear.year_1,
        )
        .first()
    )
    assert row is not None
    assert Decimal(str(row.commission_pct)) == Decimal("50.0")


def test_commission_lookup_autonomous_y2_plus(db_session):
    """autonomous_sell year_2_plus must be 30%."""
    row = (
        db_session.query(CommissionStructure)
        .filter(
            CommissionStructure.partner_category_code == "master",
            CommissionStructure.commission_type == CommissionType.autonomous_sell,
            CommissionStructure.year == CommissionYear.year_2_plus,
        )
        .first()
    )
    assert row is not None
    assert Decimal(str(row.commission_pct)) == Decimal("30.0")


def test_subpartner_uplift_only_year_1(db_session):
    """subpartner_uplift_pct = +10% in year 1, 0% in year 2+."""
    y1 = (
        db_session.query(CommissionStructure)
        .filter(
            CommissionStructure.commission_type == CommissionType.autonomous_sell,
            CommissionStructure.year == CommissionYear.year_1,
        )
        .first()
    )
    y2 = (
        db_session.query(CommissionStructure)
        .filter(
            CommissionStructure.commission_type == CommissionType.autonomous_sell,
            CommissionStructure.year == CommissionYear.year_2_plus,
        )
        .first()
    )
    assert Decimal(str(y1.subpartner_uplift_pct)) == Decimal("10.0")
    assert Decimal(str(y2.subpartner_uplift_pct)) == Decimal("0")


def test_commission_structures_internal_only(db_session):
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/config/commission-structures")
    finally:
        clear()
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 12  # 3 categories * 4 types * 2 years


def test_commission_structures_denied_for_partner_admin(db_session):
    user = make_user(UserRole.partner_admin, uuid.uuid4())
    db_session.add(user)
    db_session.commit()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/config/commission-structures")
    finally:
        clear()
    assert r.status_code == 403


def test_create_category_requires_channel_ops_admin(db_session):
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            "/config/partner-categories",
            json={
                "code": "x",
                "display_name": "X Tier",
                "deal_reg_sla_hours": 24,
                "max_discount_pct": 15,
            },
        )
    finally:
        clear()
    assert r.status_code == 403


def test_create_category_as_channel_ops_admin(db_session):
    user = make_user(UserRole.channel_ops_admin)
    db_session.add(user)
    db_session.commit()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            "/config/partner-categories",
            json={
                "code": "platinum",
                "display_name": "Platinum Tier",
                "deal_reg_sla_hours": 24,
                "max_discount_pct": 50,
            },
        )
    finally:
        clear()
    assert r.status_code == 201
    assert r.json()["code"] == "platinum"


def test_patch_commission_structure(db_session):
    user = make_user(UserRole.channel_ops_admin)
    db_session.add(user)
    db_session.commit()
    cs = db_session.query(CommissionStructure).first()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/config/commission-structures/{cs.id}",
            json={"notes": "Updated for FY26 review"},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["notes"] == "Updated for FY26 review"


def test_patch_commission_structure_denied_for_channel_manager(db_session):
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    cs = db_session.query(CommissionStructure).first()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/config/commission-structures/{cs.id}",
            json={"notes": "should fail"},
        )
    finally:
        clear()
    assert r.status_code == 403
