"""Sprint 18 / FPRM-287 — GET /internal/quotes dashboard tests."""
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
        "sqlite:///./test_internal_quotes.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_internal_quotes.db"):
        try:
            os.remove("./test_internal_quotes.db")
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
        legal_name=name or f"Org {uuid.uuid4().hex[:4]}",
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


def _quote(client, deal_id, plan="starter", qty=1, name=None):
    payload = {"feature_plan": plan, "qty_transactional_users": qty, "qty_limited_tech_users": 0}
    if name:
        payload["quote_name"] = name
    r = client.post(f"/deals/{deal_id}/quotes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ============================================================


def test_internal_quotes_returns_paginated_list(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    _quote(client, _deal(db_session, org.id).id, name="Q1")
    _quote(client, _deal(db_session, org.id).id, name="Q2")
    _quote(client, _deal(db_session, org.id).id, name="Q3")
    r = client.get("/internal/quotes")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert {it["quote_name"] for it in body["items"]} == {"Q1", "Q2", "Q3"}


def test_internal_quotes_filter_by_status(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q1 = _quote(client, _deal(db_session, org.id).id)
    q2 = _quote(client, _deal(db_session, org.id).id)
    # leave q1 draft, send q2
    r = client.patch(f"/quotes/{q2}/status", json={"status": "sent"})
    assert r.status_code == 200
    r = client.get("/internal/quotes?status=sent")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == q2


def test_internal_quotes_search_by_deal_name(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal_match = _deal(db_session, org.id, name="HotProspectDeal")
    deal_other = _deal(db_session, org.id, name="ColdLead")
    _quote(client, deal_match.id)
    _quote(client, deal_other.id)
    r = client.get("/internal/quotes?search=HotProspect")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["deal_name"] == "HotProspectDeal"


def test_internal_quotes_wrong_role_blocked(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.get("/internal/quotes")
    assert r.status_code == 403


def test_internal_quotes_summary_counts(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q_draft = _quote(client, _deal(db_session, org.id).id)
    q_sent = _quote(client, _deal(db_session, org.id).id)
    q_acc = _quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{q_sent}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q_acc}/status", json={"status": "sent"})
    # Migration 033: PATCH -> accepted now requires a quote_acceptance doc.
    import base64 as _b64
    _pdf = b"%PDF-1.4\n%%EOF"
    client.post(f"/quotes/{q_acc}/documents", json={
        "document_type": "quote_acceptance",
        "file_name": "x.pdf",
        "file_data": _b64.b64encode(_pdf).decode(),
        "file_size_bytes": len(_pdf),
    })
    client.patch(f"/quotes/{q_acc}/status", json={"status": "accepted"})
    # Migration 032: pipeline_total now requires explicit include_in_pipeline=True.
    for qid in (q_draft, q_sent, q_acc):
        client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    r = client.get("/internal/quotes")
    s = r.json()["summary"]
    assert s["total_quotes"] == 3
    assert s["draft"] == 1
    assert s["sent"] == 1
    assert s["accepted"] == 1
    assert s["pipeline_total"] > 0


def test_internal_quotes_pipeline_excludes_expired(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q1 = _quote(client, _deal(db_session, org.id).id, plan="starter", qty=1)  # ~1701
    q2 = _quote(client, _deal(db_session, org.id).id, plan="starter", qty=1)
    # Migration 032: pipeline_total now requires explicit include_in_pipeline=True.
    client.patch(f"/quotes/{q1}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q2}/pipeline-inclusion", json={"include_in_pipeline": True})
    # Move q2 to expired via sent -> expired
    client.patch(f"/quotes/{q2}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q2}/status", json={"status": "expired"})
    r = client.get("/internal/quotes")
    s = r.json()["summary"]
    assert s["expired"] == 1
    # Pipeline should only include q1's total (~ a single starter quote), not double
    one_quote = client.get(f"/quotes/{q1}").json()["active_version_data"]["grand_total_after_discount"]
    assert s["pipeline_total"] == round(float(one_quote), 2)
