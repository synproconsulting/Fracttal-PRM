"""Sprint 19 / FPRM-300 — Pricing catalogue admin CRUD API tests (AD-25).

Covers plan-price, volume-tier, and add-on CRUD; role gating; audit trail.
Story 3 (FPRM-308) tests append to the same file (audit log filter,
effective-date semantics, CSV export).
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    AddonCatalogItem,
    AuditLog,
    FeaturePlanPrice,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_pricing_admin.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_pricing_admin.db"):
        try:
            os.remove("./test_pricing_admin.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        _seed(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "audit_log",
            "addon_catalog_items",
            "volume_discount_tiers",
            "feature_plan_prices",
            "users",
        ):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db_session):
    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(db):
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(
            id=uuid.uuid4(), plan_code="starter",
            feature_pack_annual=Decimal("1161.00"),
            transactional_user_annual=Decimal("540.00"),
            limited_tech_user_annual=Decimal("240.00"),
            effective_from=today, is_active=True,
        ),
        FeaturePlanPrice(
            id=uuid.uuid4(), plan_code="professional",
            feature_pack_annual=Decimal("2868.00"),
            transactional_user_annual=Decimal("720.00"),
            limited_tech_user_annual=Decimal("240.00"),
            effective_from=today, is_active=True,
        ),
        FeaturePlanPrice(
            id=uuid.uuid4(), plan_code="enterprise",
            feature_pack_annual=Decimal("8028.00"),
            transactional_user_annual=Decimal("900.00"),
            limited_tech_user_annual=Decimal("240.00"),
            effective_from=today, is_active=True,
        ),
    ])
    db.add_all([
        VolumeDiscountTier(
            id=uuid.uuid4(), min_users=1, max_users=10,
            transactional_user_discount_pct=Decimal("0"),
            limited_tech_user_discount_pct=Decimal("0"), is_active=True,
        ),
        VolumeDiscountTier(
            id=uuid.uuid4(), min_users=11, max_users=50,
            transactional_user_discount_pct=Decimal("30"),
            limited_tech_user_discount_pct=Decimal("30"), is_active=True,
        ),
        VolumeDiscountTier(
            id=uuid.uuid4(), min_users=51, max_users=None,
            transactional_user_discount_pct=Decimal("40"),
            limited_tech_user_discount_pct=Decimal("40"), is_active=True,
        ),
    ])
    db.add_all([
        AddonCatalogItem(
            id=uuid.uuid4(), addon_key="bi_dashboards", display_name="BI Dashboards",
            monthly_price=Decimal("50.00"), available_starter=True,
            available_professional=True, included_enterprise=True, is_active=True,
        ),
        AddonCatalogItem(
            id=uuid.uuid4(), addon_key="iot_connector", display_name="IoT Connector",
            monthly_price=Decimal("100.00"), available_starter=False,
            available_professional=True, included_enterprise=True, is_active=True,
        ),
    ])
    db.commit()


def _user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(),
        email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        role=role,
        is_active=True,
        partner_org_id=org_id,
    )
    db.add(u)
    db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _first_plan(db, code="starter"):
    return (
        db.query(FeaturePlanPrice)
        .filter(FeaturePlanPrice.plan_code == code)
        .filter(FeaturePlanPrice.is_active.is_(True))
        .order_by(FeaturePlanPrice.effective_from.desc())
        .first()
    )


# --------------------------------------------------------------------------
# Feature plan price tests
# --------------------------------------------------------------------------


def test_create_plan_price(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    r = client.post("/internal/config/pricing/plans", json={
        "plan_code": "professional",
        "feature_pack_annual": "3100.00",
        "transactional_user_annual": "780.00",
        "limited_tech_user_annual": "260.00",
        "effective_from": "2026-01-01",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["plan_code"] == "professional"
    assert body["is_active"] is True
    row = db_session.query(FeaturePlanPrice).filter(FeaturePlanPrice.id == uuid.UUID(body["id"])).first()
    assert row is not None
    assert str(row.feature_pack_annual) == "3100.00"


def test_patch_plan_price_feature_pack(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    plan = _first_plan(db_session, "starter")
    r = client.patch(f"/internal/config/pricing/plans/{plan.id}", json={
        "feature_pack_annual": "1300.00",
    })
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert str(_first_plan(db_session, "starter").feature_pack_annual) == "1300.00"


def test_patch_plan_price_is_active_false_visible_via_include_inactive(client, db_session):
    admin = _user(db_session, UserRole.channel_ops_admin.value)
    _auth(admin)
    # add a replacement row first so the deactivation isn't blocked by the
    # "last active row" guard
    client.post("/internal/config/pricing/plans", json={
        "plan_code": "starter",
        "feature_pack_annual": "1200.00",
        "transactional_user_annual": "550.00",
        "limited_tech_user_annual": "245.00",
        "effective_from": "2026-06-01",
    })
    plan = (
        db_session.query(FeaturePlanPrice)
        .filter(FeaturePlanPrice.plan_code == "starter")
        .order_by(FeaturePlanPrice.effective_from)
        .first()
    )
    r = client.patch(f"/internal/config/pricing/plans/{plan.id}", json={"is_active": False})
    assert r.status_code == 200, r.text
    # default GET should not show it
    body = client.get("/internal/config/pricing/plans").json()
    assert all(p["id"] != str(plan.id) for p in body)
    # admin GET with include_inactive should show it
    body = client.get("/internal/config/pricing/plans?include_inactive=true").json()
    found = [p for p in body if p["id"] == str(plan.id)]
    assert len(found) == 1 and found[0]["is_active"] is False


def test_cannot_delete_last_active_plan_row(client, db_session):
    _auth(_user(db_session, UserRole.system_admin.value))
    plan = _first_plan(db_session, "starter")
    r = client.delete(f"/internal/config/pricing/plans/{plan.id}")
    assert r.status_code == 422
    assert "last active" in r.json()["detail"].lower()
    # row stays active
    db_session.expire_all()
    assert _first_plan(db_session, "starter").is_active is True


def test_delete_plan_price_with_multiple_active(client, db_session):
    _auth(_user(db_session, UserRole.system_admin.value))
    # add a replacement so the original can be deactivated
    r = client.post("/internal/config/pricing/plans", json={
        "plan_code": "starter",
        "feature_pack_annual": "1300.00",
        "transactional_user_annual": "550.00",
        "limited_tech_user_annual": "245.00",
        "effective_from": "2026-12-01",
    })
    assert r.status_code == 201
    new_id = r.json()["id"]
    r = client.delete(f"/internal/config/pricing/plans/{new_id}")
    assert r.status_code == 200, r.text
    db_session.expire_all()
    row = db_session.query(FeaturePlanPrice).filter(FeaturePlanPrice.id == uuid.UUID(new_id)).first()
    assert row.is_active is False


# --------------------------------------------------------------------------
# Volume discount tier tests
# --------------------------------------------------------------------------


def test_create_volume_tier_non_overlapping(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    # seeded covers 1-10 / 11-50 / 51+. Deactivate the 51+ tail first so we
    # can add a new non-overlapping band.
    tail = (
        db_session.query(VolumeDiscountTier)
        .filter(VolumeDiscountTier.min_users == 51)
        .first()
    )
    sa = _user(db_session, UserRole.system_admin.value)
    _auth(sa)
    r = client.delete(f"/internal/config/pricing/volume-tiers/{tail.id}?force=true")
    assert r.status_code == 200
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    r = client.post("/internal/config/pricing/volume-tiers", json={
        "min_users": 51, "max_users": 100,
        "transactional_user_discount_pct": "40",
        "limited_tech_user_discount_pct": "40",
    })
    assert r.status_code == 201, r.text


def test_create_overlapping_volume_tier_rejected(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    r = client.post("/internal/config/pricing/volume-tiers", json={
        "min_users": 5, "max_users": 20,
        "transactional_user_discount_pct": "10",
        "limited_tech_user_discount_pct": "10",
    })
    assert r.status_code == 422
    assert "overlap" in r.json()["detail"].lower()


def test_patch_volume_tier_discount(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    tier = db_session.query(VolumeDiscountTier).filter(VolumeDiscountTier.min_users == 11).first()
    r = client.patch(f"/internal/config/pricing/volume-tiers/{tier.id}", json={
        "transactional_user_discount_pct": "35",
    })
    assert r.status_code == 200, r.text
    db_session.expire_all()
    refreshed = db_session.query(VolumeDiscountTier).filter(VolumeDiscountTier.id == tier.id).first()
    assert Decimal(str(refreshed.transactional_user_discount_pct)) == Decimal("35")


def test_deactivate_volume_tier_with_force(client, db_session):
    _auth(_user(db_session, UserRole.system_admin.value))
    tier = db_session.query(VolumeDiscountTier).filter(VolumeDiscountTier.min_users == 11).first()
    r = client.delete(f"/internal/config/pricing/volume-tiers/{tier.id}?force=true")
    assert r.status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(VolumeDiscountTier).filter(VolumeDiscountTier.id == tier.id).first()
    assert refreshed.is_active is False
    # default GET should not include it
    body = client.get("/internal/config/pricing/volume-tiers").json()
    assert all(t["id"] != str(tier.id) for t in body)


def test_deactivate_volume_tier_gap_warning(client, db_session):
    """Removing a middle tier without ?force=true returns 422 gap warning."""
    _auth(_user(db_session, UserRole.system_admin.value))
    middle = db_session.query(VolumeDiscountTier).filter(VolumeDiscountTier.min_users == 11).first()
    r = client.delete(f"/internal/config/pricing/volume-tiers/{middle.id}")
    assert r.status_code == 422
    assert "gap" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# Add-on tests
# --------------------------------------------------------------------------


def test_create_addon(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    r = client.post("/internal/config/pricing/addons", json={
        "addon_key": "advanced_reports",
        "display_name": "Advanced Reports",
        "monthly_price": "75.00",
        "available_starter": False,
        "available_professional": True,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["addon_key"] == "advanced_reports"
    assert body["included_enterprise"] is True


def test_create_duplicate_addon_key_rejected(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    r = client.post("/internal/config/pricing/addons", json={
        "addon_key": "BI_Dashboards",  # case-insensitive duplicate of seed
        "display_name": "BI",
        "monthly_price": "10.00",
    })
    assert r.status_code == 422
    assert "already exists" in r.json()["detail"]


def test_patch_addon_monthly_price(client, db_session):
    _auth(_user(db_session, UserRole.channel_ops_admin.value))
    addon = db_session.query(AddonCatalogItem).filter(AddonCatalogItem.addon_key == "bi_dashboards").first()
    r = client.patch(f"/internal/config/pricing/addons/{addon.id}", json={"monthly_price": "65.00"})
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert str(
        db_session.query(AddonCatalogItem).filter(AddonCatalogItem.id == addon.id).first().monthly_price
    ) == "65.00"
    # audit captured
    log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "pricing.addon_updated")
        .first()
    )
    assert log is not None
    assert log.object_id == addon.id


def test_deactivate_addon(client, db_session):
    _auth(_user(db_session, UserRole.system_admin.value))
    addon = db_session.query(AddonCatalogItem).filter(AddonCatalogItem.addon_key == "iot_connector").first()
    r = client.delete(f"/internal/config/pricing/addons/{addon.id}")
    assert r.status_code == 200
    body = client.get("/internal/config/pricing/addons").json()
    assert all(a["id"] != str(addon.id) for a in body)


# --------------------------------------------------------------------------
# Role gating
# --------------------------------------------------------------------------


def test_channel_manager_cannot_write_plan_price(client, db_session):
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.post("/internal/config/pricing/plans", json={
        "plan_code": "starter",
        "feature_pack_annual": "1.00",
        "transactional_user_annual": "1.00",
        "limited_tech_user_annual": "1.00",
        "effective_from": "2026-01-01",
    })
    assert r.status_code == 403


def test_partner_admin_cannot_access_volume_tiers(client, db_session):
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=uuid.uuid4()))
    # plain GET is allowed for any authenticated user; ?include_inactive is admin-only
    r = client.get("/internal/config/pricing/volume-tiers?include_inactive=true")
    assert r.status_code == 403


def test_include_inactive_requires_admin(client, db_session):
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.get("/internal/config/pricing/plans?include_inactive=true")
    assert r.status_code == 403


def test_audit_log_on_every_write(client, db_session):
    admin = _user(db_session, UserRole.channel_ops_admin.value)
    _auth(admin)
    # POST plan
    r = client.post("/internal/config/pricing/plans", json={
        "plan_code": "enterprise",
        "feature_pack_annual": "9000.00",
        "transactional_user_annual": "950.00",
        "limited_tech_user_annual": "250.00",
        "effective_from": "2026-01-01",
    })
    assert r.status_code == 201
    new_plan_id = uuid.UUID(r.json()["id"])
    # PATCH plan
    r = client.patch(f"/internal/config/pricing/plans/{new_plan_id}", json={
        "feature_pack_annual": "9100.00",
    })
    assert r.status_code == 200
    # POST addon
    r = client.post("/internal/config/pricing/addons", json={
        "addon_key": "audit_pack",
        "display_name": "Audit Pack",
        "monthly_price": "30.00",
    })
    assert r.status_code == 201
    addon_id = uuid.UUID(r.json()["id"])
    # PATCH addon
    r = client.patch(f"/internal/config/pricing/addons/{addon_id}", json={"display_name": "Audit Pack v2"})
    assert r.status_code == 200
    actions = {
        log.action
        for log in db_session.query(AuditLog).filter(AuditLog.action.like("pricing.%")).all()
    }
    assert "pricing.plan_price_created" in actions
    assert "pricing.plan_price_updated" in actions
    assert "pricing.addon_created" in actions
    assert "pricing.addon_updated" in actions


# FPRM-308 tests (audit log filter + effective-date semantics + CSV export)
# are appended to this file in the Sprint 19 Story 3 PR.
