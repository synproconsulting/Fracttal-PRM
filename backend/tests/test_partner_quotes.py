"""Sprint 18 / FPRM-291 — GET /partners/{id}/quotes tests."""
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
    User,
    VolumeDiscountTier,
)
from roles import UserRole


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_partner_quotes.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_partner_quotes.db"):
        try:
            os.remove("./test_partner_quotes.db")
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


def _seed(db):
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
    db.commit()


def _org(db, name=None):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=name or f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o); db.commit()
    return o


def _deal(db, org_id, name=None):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status="approved",
        customer_name="C", deal_name=name or "D",
    )
    db.add(d); db.commit()
    return d


def _user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _quote(client, deal_id, plan="starter"):
    r = client.post(f"/deals/{deal_id}/quotes", json={
        "feature_plan": plan, "qty_transactional_users": 1, "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ============================================================


def test_partner_quotes_returns_own_org(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    _auth(_user(db_session, UserRole.channel_manager.value))
    _quote(client, deal.id)
    _quote(client, deal.id)
    partner = _user(db_session, UserRole.partner_admin.value, org_id=org.id)
    _auth(partner)
    r = client.get(f"/partners/{org.id}/quotes")
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2


def test_partner_quotes_other_org_blocked(client, db_session):
    org_a = _org(db_session)
    org_b = _org(db_session)
    deal_a = _deal(db_session, org_a.id)
    _auth(_user(db_session, UserRole.channel_manager.value))
    _quote(client, deal_a.id)
    partner_b = _user(db_session, UserRole.partner_admin.value, org_id=org_b.id)
    _auth(partner_b)
    r = client.get(f"/partners/{org_a.id}/quotes")
    assert r.status_code == 403


def test_partner_quotes_empty_org_returns_empty_list(client, db_session):
    org = _org(db_session)
    partner = _user(db_session, UserRole.partner_admin.value, org_id=org.id)
    _auth(partner)
    r = client.get(f"/partners/{org.id}/quotes")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_partner_quotes_active_version_grand_total(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _quote(client, deal.id, plan="professional")
    active = client.get(f"/quotes/{qid}").json()["active_version_data"]
    partner = _user(db_session, UserRole.partner_admin.value, org_id=org.id)
    _auth(partner)
    r = client.get(f"/partners/{org.id}/quotes")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["grand_total_after_discount"] == float(active["grand_total_after_discount"])


def test_internal_user_blocked_from_partner_endpoint(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.get(f"/partners/{org.id}/quotes")
    assert r.status_code == 403
    body = r.json()
    assert "/internal/quotes" in body["detail"]
