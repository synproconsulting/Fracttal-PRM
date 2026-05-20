"""Tests for Sprint 15 / FPRM-246 quotes_router."""
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
    AuditLog,
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
        "sqlite:///./test_quotes_api.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_quotes_api.db"):
        try:
            os.remove("./test_quotes_api.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        seed_pricing(s)
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


def seed_pricing(db):
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
    for key, name, price, in_starter, in_pro in [
        ("first_tranche_assets",  "First Tranche of Assets",  Decimal("95.00"), True,  True),
        ("fracttal_hub",          "FRACTTAL_HUB",              Decimal("55.00"), True,  True),
        ("trainable_ai_bot",      "Trainable AI Bot",          Decimal("95.00"), False, True),
        ("advanced_warehouse",    "Advanced Warehouse",        Decimal("95.00"), False, True),
    ]:
        db.add(AddonCatalogItem(
            addon_key=key, display_name=name, monthly_price=price,
            available_starter=in_starter, available_professional=in_pro,
            included_enterprise=True, is_active=True,
        ))
    db.commit()


def make_user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u)
    db.commit()
    return u


def make_org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o)
    db.commit()
    return o


def make_deal(db, org_id, status="approved"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", deal_name="D",
    )
    db.add(d)
    db.commit()
    return d


def auth(client, user):
    app.dependency_overrides[get_current_user] = lambda: user


# ============================================================
# Tests
# ============================================================


def test_create_quote_from_deal_persists_version_and_lines(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    user = make_user(db_session, UserRole.channel_manager.value)
    auth(client, user)
    r = client.post(f"/deals/{deal.id}/quotes", json={
        "quote_name": "Initial quote",
        "currency_code": "USD",
        "feature_plan": "enterprise",
        "feature_plan_discount_pct": 0,
        "qty_transactional_users": 5,
        "qty_limited_tech_users": 25,
        "selected_addon_keys": [],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["active_version"] == 1
    av = body["active_version_data"]
    assert av["version_number"] == 1
    assert len(av["line_items"]) >= 4
    # Grand total matches Story 2 spec example 1
    assert float(av["grand_total_after_discount"]) == 16608.00


def test_create_quote_with_scenario_label(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    r = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
        "scenario_label": "best",
    })
    assert r.status_code == 201
    assert r.json()["active_scenario"] == "best"
    assert r.json()["active_version_data"]["scenario_label"] == "best"


def test_get_deal_quotes_list_returns_summary(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
    })
    r = client.get(f"/deals/{deal.id}/quotes")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["grand_total_after_discount"] is not None


def test_get_quote_detail_includes_line_items(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    created = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 2,
        "qty_limited_tech_users": 0,
    }).json()
    qid = created["id"]
    r = client.get(f"/quotes/{qid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == qid
    av = body["active_version_data"]
    # line_order must be sequential starting from 1
    orders = [li["line_order"] for li in av["line_items"]]
    assert orders == sorted(orders)
    assert orders[0] == 1


def test_add_second_version_does_not_change_active_version(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    r = client.post(f"/quotes/{qid}/versions", json={
        "feature_plan": "professional",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201
    assert r.json()["version_number"] == 2
    # active_version still 1
    q = client.get(f"/quotes/{qid}").json()
    assert q["active_version"] == 1


def test_set_active_version_to_2(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    client.post(f"/quotes/{qid}/versions", json={
        "feature_plan": "professional",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    r = client.patch(f"/quotes/{qid}/active-version", json={"version_number": 2})
    assert r.status_code == 200
    assert r.json()["active_version"] == 2


def test_partner_admin_blocked_from_other_orgs_deal(client, db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    deal_a = make_deal(db_session, org_a.id)
    partner_b = make_user(db_session, UserRole.partner_admin.value, org_id=org_b.id)
    auth(client, partner_b)
    r = client.post(f"/deals/{deal_a.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    assert r.status_code == 403


def test_partner_admin_can_quote_own_deal(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    partner = make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    auth(client, partner)
    r = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201


def test_status_transition_draft_to_sent_succeeds(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    r = client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"


def test_status_transition_sent_to_draft_rejected(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    r = client.patch(f"/quotes/{qid}/status", json={"status": "draft"})
    assert r.status_code == 422


def test_soft_delete_version(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.system_admin.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    client.post(f"/quotes/{qid}/versions", json={
        "feature_plan": "professional",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    r = client.delete(f"/quotes/{qid}/versions/2")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is True
    versions = client.get(f"/quotes/{qid}/versions").json()
    by_num = {v["version_number"]: v for v in versions}
    assert by_num[2]["is_deleted"] is True


def test_cannot_delete_active_version(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.system_admin.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    r = client.delete(f"/quotes/{qid}/versions/1")
    assert r.status_code == 422


def test_pricing_plans_endpoint_returns_three(client, db_session):
    auth(client, make_user(db_session, UserRole.partner_user.value))
    r = client.get("/internal/config/pricing/plans")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3
    assert {p["plan_code"] for p in body} == {"starter", "professional", "enterprise"}


def test_addons_endpoint(client, db_session):
    auth(client, make_user(db_session, UserRole.partner_user.value))
    r = client.get("/internal/config/pricing/addons")
    assert r.status_code == 200
    assert len(r.json()) >= 4  # the 4 we seeded in this test module


def test_create_quote_deal_not_found(client, db_session):
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    fake_id = uuid.uuid4()
    r = client.post(f"/deals/{fake_id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    assert r.status_code == 404


def test_audit_log_on_create(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "quote.created" in actions


def test_enterprise_with_addon_returns_422(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    r = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "enterprise",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
        "selected_addon_keys": ["fracttal_hub"],
    })
    assert r.status_code == 422


def test_set_active_version_to_soft_deleted_rejected(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.system_admin.value))
    qid = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    }).json()["id"]
    # add v2, then delete v2; activating it should 422
    client.post(f"/quotes/{qid}/versions", json={
        "feature_plan": "professional",
        "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    # Move active to v2 so we can delete v1, then re-active v1 should still 422
    client.patch(f"/quotes/{qid}/active-version", json={"version_number": 2})
    client.delete(f"/quotes/{qid}/versions/1")
    r = client.patch(f"/quotes/{qid}/active-version", json={"version_number": 1})
    assert r.status_code == 422
