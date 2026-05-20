"""Sprint 18 / FPRM-283 — Quote scenario endpoint tests."""
import os
import sys
import uuid
from datetime import date
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
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    ProgramType,
    Quote,
    QuoteVersion,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_quote_scenarios.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_quote_scenarios.db"):
        try:
            os.remove("./test_quote_scenarios.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        _seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "quote_line_items", "quote_versions", "quotes",
            "addon_catalog_items", "volume_discount_tiers", "feature_plan_prices",
            "deal_registrations", "users", "partner_organizations", "audit_log",
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


def _seed_pricing(db):
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter",      feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise",   feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1,   max_users=10,   transactional_user_discount_pct=Decimal("0"),  limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11,  max_users=50,   transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51,  max_users=100,  transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300,  transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500,  transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    db.add(AddonCatalogItem(
        addon_key="fracttal_hub", display_name="FRACTTAL_HUB", monthly_price=Decimal("55.00"),
        available_starter=True, available_professional=True, included_enterprise=True, is_active=True,
    ))
    db.commit()


def _make_org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o); db.commit()
    return o


def _make_deal(db, org_id, status="approved"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", deal_name="D",
    )
    db.add(d); db.commit()
    return d


def _make_user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _create_quote(client, deal_id, scenario=None):
    payload = {
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
    }
    if scenario:
        payload["scenario_label"] = scenario
    r = client.post(f"/deals/{deal_id}/quotes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_version(client, quote_id, scenario, feature_plan="professional"):
    r = client.post(f"/quotes/{quote_id}/versions", json={
        "feature_plan": feature_plan,
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
        "scenario_label": scenario,
    })
    assert r.status_code == 201, r.text
    return r.json()["version_number"]


# ============================================================
# GET /quotes/{id}/scenarios
# ============================================================


def test_get_scenarios_empty(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id)  # no scenario
    r = client.get(f"/quotes/{qid}/scenarios")
    assert r.status_code == 200
    body = r.json()
    assert body["scenarios"] == []
    assert body["active_scenario"] is None


def test_get_scenarios_one_label(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="best")
    r = client.get(f"/quotes/{qid}/scenarios")
    body = r.json()
    assert len(body["scenarios"]) == 1
    assert body["scenarios"][0]["scenario_label"] == "best"
    assert body["scenarios"][0]["version_number"] == 1
    assert body["scenarios"][0]["is_active"] is True  # active_scenario set on create


def test_get_scenarios_three_labels_in_order(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")
    _add_version(client, qid, "better")
    _add_version(client, qid, "best")
    r = client.get(f"/quotes/{qid}/scenarios")
    body = r.json()
    assert [s["scenario_label"] for s in body["scenarios"]] == ["good", "better", "best"]


def test_get_scenarios_latest_version_wins(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")  # v1
    v2 = _add_version(client, qid, "good")  # v2 also "good"
    r = client.get(f"/quotes/{qid}/scenarios")
    body = r.json()
    assert len(body["scenarios"]) == 1
    assert body["scenarios"][0]["scenario_label"] == "good"
    assert body["scenarios"][0]["version_number"] == v2  # higher version wins


def test_get_scenarios_partner_admin_own_org(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="best")
    partner = _make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    _auth(partner)
    r = client.get(f"/quotes/{qid}/scenarios")
    assert r.status_code == 200
    assert len(r.json()["scenarios"]) == 1


def test_get_scenarios_partner_admin_other_org_blocked(client, db_session):
    org_a = _make_org(db_session)
    org_b = _make_org(db_session)
    deal_a = _make_deal(db_session, org_a.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal_a.id, scenario="best")
    partner_b = _make_user(db_session, UserRole.partner_admin.value, org_id=org_b.id)
    _auth(partner_b)
    r = client.get(f"/quotes/{qid}/scenarios")
    assert r.status_code == 403


# ============================================================
# PATCH /quotes/{id}/active-scenario
# ============================================================


def test_patch_active_scenario_sets_correctly(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")
    _add_version(client, qid, "best")

    r = client.patch(f"/quotes/{qid}/active-scenario", json={"scenario_label": "best"})
    assert r.status_code == 200
    assert r.json()["active_scenario"] == "best"

    r2 = client.get(f"/quotes/{qid}/scenarios")
    by_label = {s["scenario_label"]: s for s in r2.json()["scenarios"]}
    assert by_label["best"]["is_active"] is True
    assert by_label["good"]["is_active"] is False


def test_patch_active_scenario_invalid_label_returns_422(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")
    r = client.patch(f"/quotes/{qid}/active-scenario", json={"scenario_label": "best"})
    assert r.status_code == 422


def test_patch_active_scenario_null_clears(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")
    r = client.patch(f"/quotes/{qid}/active-scenario", json={"scenario_label": None})
    assert r.status_code == 200
    assert r.json()["active_scenario"] is None


def test_patch_scenario_wrong_role_returns_403(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    _auth(_make_user(db_session, UserRole.channel_manager.value))
    qid = _create_quote(client, deal.id, scenario="good")
    partner = _make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    _auth(partner)
    r = client.patch(f"/quotes/{qid}/active-scenario", json={"scenario_label": "good"})
    assert r.status_code == 403
