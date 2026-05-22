"""Tests for the ``won`` deal status, the cascade-cancel behaviour on terminal
deal transitions, the ``suggest_mark_won`` response flag, and the new
``won_deals`` / ``closed_won_value`` summary fields on ``GET /internal/quotes``.

Spec covered:
* approved → won allowed (POST /internal/deals/{id}/won, 200)
* won is terminal — won → lost / won → withdrawn / won → approved all 422
* Lost cascade: draft/sent quotes cancelled with note "Deal marked as lost"
* Withdrawn cascade: same, with note "Deal marked as withdrawn"
* Won cascade: draft/sent cancelled with note "Deal marked as won", accepted preserved
* All cascaded quotes have include_in_pipeline cleared
* Accepted-quote response includes suggest_mark_won when conditions met
* Won deals excluded from pipeline_total
* closed_won_value sums accepted quotes on won deals
* partner_admin cannot call POST /internal/deals/{id}/won (403)
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
    AuditLog,
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    Quote,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


DB_PATH = "./test_deal_won_cascade.db"


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


def _deal(db, org_id, *, status="approved"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", deal_name=f"D-{uuid.uuid4().hex[:4]}",
        estimated_deal_value=Decimal("10000.00"),
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


# ============================================================
# State machine
# ============================================================


def test_approved_to_won_allowed(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    r = client.post(f"/internal/deals/{deal.id}/won")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "won"


def test_won_is_terminal_via_status_patch(client, db_session):
    """Once won, the PATCH /deal-registrations/{id}/status endpoint refuses
    every supported transition (lost / withdrawn). The endpoint already
    enforces this because ``won`` is not in any allowed-source-status set."""
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    client.post(f"/internal/deals/{deal.id}/won")
    for target in ("lost", "withdrawn"):
        r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": target})
        assert r.status_code == 422, f"Expected 422 for won → {target}, got {r.status_code}: {r.text}"


def test_won_endpoint_rejects_non_approved_sources(client, db_session):
    """POST /internal/deals/{id}/won must reject every non-approved source."""
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    for src in ("draft", "submitted", "under_review", "rejected"):
        d = _deal(db_session, org.id, status=src)
        r = client.post(f"/internal/deals/{d.id}/won")
        assert r.status_code == 422, f"won-from-{src} should be 422, got {r.status_code}"


# ============================================================
# Cascade — won
# ============================================================


def test_won_cascade_cancels_draft_and_sent_preserves_accepted(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q_draft = _make_quote(client, deal.id)
    q_sent = _make_quote(client, deal.id)
    q_acc = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q_sent}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q_acc}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q_acc}/status", json={"status": "accepted"})

    r = client.post(f"/internal/deals/{deal.id}/won")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "won"
    assert body["cascaded_cancelled_quotes"] == 2

    assert client.get(f"/quotes/{q_draft}").json()["status"] == "cancelled"
    assert client.get(f"/quotes/{q_sent}").json()["status"] == "cancelled"
    assert client.get(f"/quotes/{q_acc}").json()["status"] == "accepted"


def test_won_cascade_clears_include_in_pipeline(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q}/pipeline-inclusion", json={"include_in_pipeline": True})
    assert client.get(f"/quotes/{q}").json()["include_in_pipeline"] is True

    client.post(f"/internal/deals/{deal.id}/won")
    after = client.get(f"/quotes/{q}").json()
    assert after["status"] == "cancelled"
    assert after["include_in_pipeline"] is False


def test_won_cascade_emits_quote_cancelled_audit_with_note(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)

    client.post(f"/internal/deals/{deal.id}/won")
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "quote.cancelled", AuditLog.object_id == uuid.UUID(q))
        .all()
    )
    assert len(audit) == 1
    assert audit[0].notes == "Deal marked as won"


# ============================================================
# Cascade — lost / withdrawn
# ============================================================


def test_lost_cascade_cancels_draft_and_sent(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q_draft = _make_quote(client, deal.id)
    q_sent = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q_sent}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q_sent}/pipeline-inclusion", json={"include_in_pipeline": True})

    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "lost"})
    assert r.status_code == 200, r.text
    assert client.get(f"/quotes/{q_draft}").json()["status"] == "cancelled"
    sent_after = client.get(f"/quotes/{q_sent}").json()
    assert sent_after["status"] == "cancelled"
    assert sent_after["include_in_pipeline"] is False

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "quote.cancelled")
        .all()
    )
    notes = sorted(a.notes for a in audit)
    assert notes == ["Deal marked as lost", "Deal marked as lost"]


def test_withdrawn_cascade_cancels_draft_and_sent(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q}/pipeline-inclusion", json={"include_in_pipeline": True})

    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "withdrawn"})
    assert r.status_code == 200, r.text
    after = client.get(f"/quotes/{q}").json()
    assert after["status"] == "cancelled"
    assert after["include_in_pipeline"] is False

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "quote.cancelled", AuditLog.object_id == uuid.UUID(q))
        .first()
    )
    assert audit is not None
    assert audit.notes == "Deal marked as withdrawn"


# ============================================================
# Auto-suggest on quote acceptance
# ============================================================


def test_accept_quote_returns_suggest_mark_won_when_no_pending_quotes(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q}/status", json={"status": "sent"})

    r = client.patch(f"/quotes/{q}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["suggest_mark_won"] is True


def test_accept_quote_returns_no_suggest_when_pending_quote_exists(client, db_session):
    """If another draft/sent quote still exists on the deal, do not suggest
    closing as Won (the reviewer presumably still has work in flight)."""
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q_acc = _make_quote(client, deal.id)
    _make_quote(client, deal.id)  # second quote, stays draft
    client.patch(f"/quotes/{q_acc}/status", json={"status": "sent"})

    r = client.patch(f"/quotes/{q_acc}/status", json={"status": "accepted"})
    assert r.status_code == 200
    assert r.json()["suggest_mark_won"] is False


# ============================================================
# Summary
# ============================================================


def test_won_deals_excluded_from_pipeline_total(client, db_session):
    """An accepted quote with include_in_pipeline=True on a won deal must
    not contribute to pipeline_total (it's closed-won, not pipeline)."""
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q}/status", json={"status": "accepted"})
    # Pre-won: the accepted quote IS in pipeline_total
    pre = client.get("/internal/quotes").json()["summary"]
    assert pre["pipeline_total"] > 0
    # Post-won: pipeline_total drops to 0; the value moves to closed_won_value
    client.post(f"/internal/deals/{deal.id}/won")
    post = client.get("/internal/quotes").json()["summary"]
    assert post["pipeline_total"] == 0


def test_closed_won_value_sums_accepted_quotes_on_won_deals(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id, status="approved")
    q = _make_quote(client, deal.id)
    client.patch(f"/quotes/{q}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q}/status", json={"status": "accepted"})
    expected = round(_quote_total(client, q), 2)

    client.post(f"/internal/deals/{deal.id}/won")
    summary = client.get("/internal/quotes").json()["summary"]
    assert summary["won_deals"] == 1
    assert summary["closed_won_value"] == pytest.approx(expected, rel=1e-9)


# ============================================================
# Auth
# ============================================================


def test_partner_admin_cannot_mark_deal_won(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="approved")
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.post(f"/internal/deals/{deal.id}/won")
    assert r.status_code == 403, r.text
