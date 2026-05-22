"""Pipeline-total aggregation on deal list endpoints.

Verifies the per-deal ``pipeline_total`` field added in PR (post-#149):
* ``GET /internal/deals``
* ``GET /deal-registrations`` (portal list)
* ``GET /partners/{partner_id}/pipeline`` (partner kanban)

Semantics:
* Sum of ``grand_total_after_discount`` from the *active*, non-deleted
  version of each Quote where ``include_in_pipeline=True`` AND
  ``status NOT IN ('expired', 'cancelled')``.
* Deal has no qualifying quotes → ``pipeline_total`` is ``None``.
* Deal has zero matching quotes (none opted in) → ``pipeline_total`` is ``None``,
  not 0.0 — callers distinguish "no included quotes" from "zero".
"""
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
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


DB_PATH = "./test_deal_pipeline_total.db"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
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
        FeaturePlanPrice(plan_code="starter", feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise", feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1, max_users=10, transactional_user_discount_pct=Decimal("0"), limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11, max_users=50, transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51, max_users=100, transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300, transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500, transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    db.commit()


def _org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:4]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(o); db.commit()
    return o


def _deal(db, org_id, *, status="submitted", value=Decimal("10000.00")):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", deal_name=f"D-{uuid.uuid4().hex[:4]}",
        estimated_deal_value=value,
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


def _make_quote(client, deal_id):
    r = client.post(f"/deals/{deal_id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _quote_total(client, quote_id):
    r = client.get(f"/quotes/{quote_id}")
    assert r.status_code == 200
    return float(r.json()["active_version_data"]["grand_total_after_discount"])


def _find(items, deal_id):
    return next(d for d in items if d["id"] == str(deal_id))


# ---------- /internal/deals ----------

def test_internal_deals_pipeline_total_none_when_no_included_quotes(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    _make_quote(client, deal.id)  # default include_in_pipeline=False

    r = client.get("/internal/deals")
    assert r.status_code == 200, r.text
    row = _find(r.json()["items"], deal.id)
    assert row["pipeline_total"] is None


def test_internal_deals_pipeline_total_sums_included_quote_active_versions(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    q1 = _make_quote(client, deal.id)
    q2 = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q1}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q2}/pipeline-inclusion", json={"include_in_pipeline": True})
    expected = round(_quote_total(client, q1) + _quote_total(client, q2), 2)

    r = client.get("/internal/deals")
    row = _find(r.json()["items"], deal.id)
    assert row["pipeline_total"] == pytest.approx(expected, rel=1e-9)


def test_internal_deals_pipeline_total_excludes_expired_and_cancelled(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    keep = _make_quote(client, deal.id)
    cancelled = _make_quote(client, deal.id)
    expired = _make_quote(client, deal.id)
    for qid in (keep, cancelled, expired):
        client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{cancelled}/status", json={"status": "cancelled"})
    client.patch(f"/quotes/{expired}/status", json={"status": "sent"})
    client.patch(f"/quotes/{expired}/status", json={"status": "expired"})

    r = client.get("/internal/deals")
    row = _find(r.json()["items"], deal.id)
    assert row["pipeline_total"] == pytest.approx(_quote_total(client, keep), rel=1e-9)


# ---------- /deal-registrations (portal list) ----------

def test_portal_deals_includes_pipeline_total_for_own_org(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    # Channel manager opts the quote in
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, deal.id)
    client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    expected = round(_quote_total(client, qid), 2)

    # Partner_admin fetches their org's deal list
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.get("/deal-registrations")
    assert r.status_code == 200, r.text
    row = _find(r.json()["items"], deal.id)
    assert row["pipeline_total"] == pytest.approx(expected, rel=1e-9)


def test_portal_deals_pipeline_total_none_when_no_quotes(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.get("/deal-registrations")
    row = _find(r.json()["items"], deal.id)
    assert row["pipeline_total"] is None


# ---------- /partners/{id}/pipeline (kanban) ----------

def test_partner_pipeline_kanban_includes_pipeline_total(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="submitted")
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, deal.id)
    client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    expected = round(_quote_total(client, qid), 2)

    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.get(f"/partners/{org.id}/pipeline")
    assert r.status_code == 200, r.text
    body = r.json()
    bucket = body.get("submitted", [])
    assert any(d["id"] == str(deal.id) for d in bucket)
    row = next(d for d in bucket if d["id"] == str(deal.id))
    assert row["pipeline_total"] == pytest.approx(expected, rel=1e-9)
