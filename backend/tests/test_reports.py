"""FPRM-221 — tests for /internal/reports endpoints (Sprint 14)."""
import os
import sys
import uuid
from datetime import date, datetime, timedelta

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
    DealRegistration,
    PartnerActivationChecklist,
    PartnerOrganization,
    PartnerCategory,
    PartnerStatus,
    PartnerTier,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_reports.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_reports.db"):
        try:
            os.remove("./test_reports.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _make_user(db_session, role: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name=f"User {role}",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_partner(
    db_session,
    legal_name: str = "Acme Co",
    partner_category: PartnerCategory = PartnerCategory.master,
    tier: PartnerTier = None,
    status: PartnerStatus = PartnerStatus.active,
) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type=ProgramType.distributor,
        partner_category=partner_category,
        tier=tier,
        status=status,
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_deal(
    db_session,
    partner_org_id,
    status: str,
    estimated_value: float = None,
    submitted_at: datetime = None,
    reviewed_at: datetime = None,
    conflict_status: str = "not_checked",
    customer_domain: str = None,
    commission_rate_snapshot: float = None,
) -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status=status,
        customer_name="Some Customer",
        customer_domain=customer_domain,
        deal_name=f"Deal {uuid.uuid4().hex[:6]}",
        estimated_deal_value=estimated_value,
        estimated_close_date=date.today(),
        conflict_status=conflict_status,
        submitted_at=submitted_at,
        reviewed_at=reviewed_at,
        commission_rate_snapshot=commission_rate_snapshot,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def _override(role: str = UserRole.system_admin.value):
    user = User(id=uuid.uuid4(), email="x@x.x", hashed_password="x", role=role, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    return user


# ---------------- /pipeline ----------------

def test_pipeline_returns_zero_when_db_empty(client, db_session):
    _override()
    r = client.get("/internal/reports/pipeline")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["by_partner"] == []
    assert body["by_category"] == []
    assert body["by_tier"] == []
    assert body["totals"] == {
        "total_deals": 0,
        "approved": 0,
        "rejected": 0,
        "under_review": 0,
        "total_value": 0.0,
    }


def test_pipeline_counts_total_deals(client, db_session):
    _override()
    org = _make_partner(db_session)
    _make_deal(db_session, org.id, "submitted", 1000.0, submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "approved", 5000.0, submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "rejected", 2000.0, submitted_at=datetime.utcnow())

    r = client.get("/internal/reports/pipeline")
    body = r.json()
    assert body["totals"]["total_deals"] == 3
    assert body["totals"]["approved"] == 1
    assert body["totals"]["rejected"] == 1
    assert body["totals"]["total_value"] == 8000.0


def test_pipeline_approved_count(client, db_session):
    _override()
    org = _make_partner(db_session)
    _make_deal(db_session, org.id, "approved", 100.0, submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "approved", 200.0, submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "submitted", 50.0, submitted_at=datetime.utcnow())

    body = client.get("/internal/reports/pipeline").json()
    assert body["totals"]["approved"] == 2
    by_partner = body["by_partner"]
    assert len(by_partner) == 1
    assert by_partner[0]["approved"] == 2
    assert by_partner[0]["total_deals"] == 3


def test_pipeline_from_date_filter_excludes_older_deals(client, db_session):
    _override()
    org = _make_partner(db_session)
    old = datetime.utcnow() - timedelta(days=60)
    new = datetime.utcnow()
    _make_deal(db_session, org.id, "approved", 999.0, submitted_at=old)
    _make_deal(db_session, org.id, "approved", 111.0, submitted_at=new)

    cutoff = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    body = client.get(f"/internal/reports/pipeline?from_date={cutoff}").json()
    assert body["totals"]["total_deals"] == 1
    assert body["totals"]["total_value"] == 111.0


def test_pipeline_partner_category_filter(client, db_session):
    _override()
    org_master = _make_partner(db_session, partner_category=PartnerCategory.master)
    org_promotor = _make_partner(db_session, partner_category=PartnerCategory.promotor)
    _make_deal(db_session, org_master.id, "approved", 100.0, submitted_at=datetime.utcnow())
    _make_deal(db_session, org_promotor.id, "approved", 200.0, submitted_at=datetime.utcnow())

    body = client.get("/internal/reports/pipeline?partner_category=master").json()
    assert body["totals"]["total_deals"] == 1
    assert body["totals"]["total_value"] == 100.0


# ---------------- /cycle-times ----------------

def test_cycle_times_overall_avg_null_when_no_completed(client, db_session):
    _override()
    org = _make_partner(db_session)
    _make_deal(db_session, org.id, "submitted", 100.0, submitted_at=datetime.utcnow())
    body = client.get("/internal/reports/cycle-times").json()
    assert body["overall_avg_days"] is None
    assert body["slowest_deals"] == []


def test_cycle_times_correct_average_with_two_completed(client, db_session):
    _override()
    org = _make_partner(db_session)
    sub_a = datetime(2026, 1, 1, 0, 0, 0)
    rev_a = sub_a + timedelta(days=2)  # 2 days
    sub_b = datetime(2026, 2, 1, 0, 0, 0)
    rev_b = sub_b + timedelta(days=4)  # 4 days
    _make_deal(db_session, org.id, "approved", 1.0, submitted_at=sub_a, reviewed_at=rev_a)
    _make_deal(db_session, org.id, "rejected", 1.0, submitted_at=sub_b, reviewed_at=rev_b)

    body = client.get("/internal/reports/cycle-times").json()
    assert body["overall_avg_days"] == 3.0


def test_cycle_times_slowest_deals_sorted_desc_top_5(client, db_session):
    _override()
    org = _make_partner(db_session)
    for days in (1, 2, 3, 4, 5, 6, 7):
        sub = datetime(2026, 1, 1)
        rev = sub + timedelta(days=days)
        _make_deal(db_session, org.id, "approved", 1.0, submitted_at=sub, reviewed_at=rev)

    body = client.get("/internal/reports/cycle-times").json()
    assert len(body["slowest_deals"]) == 5
    days_list = [s["days_to_decision"] for s in body["slowest_deals"]]
    assert days_list == sorted(days_list, reverse=True)
    assert days_list[0] == 7.0


# ---------------- /conflicts ----------------

def test_conflicts_rate_zero_when_no_deals(client, db_session):
    _override()
    body = client.get("/internal/reports/conflicts").json()
    assert body["conflict_rate_pct"] == 0.0
    assert body["total_deals"] == 0
    assert body["conflict_count"] == 0
    assert body["unresolved_conflicts"] == []


def test_conflicts_counts_conflict_detected_correctly(client, db_session):
    _override()
    org = _make_partner(db_session)
    _make_deal(db_session, org.id, "submitted", 1.0, submitted_at=datetime.utcnow(), conflict_status="clear")
    _make_deal(db_session, org.id, "under_review", 1.0, submitted_at=datetime.utcnow(), conflict_status="conflict_detected")
    _make_deal(db_session, org.id, "under_review", 1.0, submitted_at=datetime.utcnow(), conflict_status="conflict_detected")

    body = client.get("/internal/reports/conflicts").json()
    assert body["total_deals"] == 3
    assert body["conflict_count"] == 2
    assert body["conflict_rate_pct"] == round(2 / 3 * 100, 1)


def test_conflicts_unresolved_excludes_approved_and_rejected(client, db_session):
    _override()
    org = _make_partner(db_session)
    _make_deal(db_session, org.id, "approved", 1.0, submitted_at=datetime.utcnow(), conflict_status="conflict_detected")
    _make_deal(db_session, org.id, "rejected", 1.0, submitted_at=datetime.utcnow(), conflict_status="conflict_detected")
    _make_deal(db_session, org.id, "under_review", 1.0, submitted_at=datetime.utcnow(), conflict_status="conflict_detected")

    body = client.get("/internal/reports/conflicts").json()
    # all three are conflict_detected
    assert body["conflict_count"] == 3
    # but only the under_review one is unresolved
    assert len(body["unresolved_conflicts"]) == 1
    assert body["unresolved_conflicts"][0]["deal_name"]


# ---------------- /pipeline/export ----------------

def test_export_returns_200(client, db_session):
    _override()
    r = client.get("/internal/reports/pipeline/export")
    assert r.status_code == 200


def test_export_content_type_csv(client, db_session):
    _override()
    r = client.get("/internal/reports/pipeline/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"].lower()


def test_export_first_line_is_header(client, db_session):
    _override()
    r = client.get("/internal/reports/pipeline/export")
    first_line = r.text.split("\r\n", 1)[0].split("\n", 1)[0]
    expected = "Partner Name,Category,Tier,Deal Name,Customer Name,Deal Value,Status,Submitted Date,Approved Date,Commission Rate"
    assert first_line == expected


# ---------------- Role gating ----------------

def test_channel_manager_can_get_pipeline(client, db_session):
    _override(UserRole.channel_manager.value)
    r = client.get("/internal/reports/pipeline")
    assert r.status_code == 200


def test_partner_admin_gets_403_on_pipeline(client, db_session):
    _override(UserRole.partner_admin.value)
    r = client.get("/internal/reports/pipeline")
    assert r.status_code == 403


def test_finance_approver_can_export(client, db_session):
    _override(UserRole.finance_approver.value)
    r = client.get("/internal/reports/pipeline/export")
    assert r.status_code == 200


def test_finance_approver_gets_403_on_pipeline(client, db_session):
    _override(UserRole.finance_approver.value)
    r = client.get("/internal/reports/pipeline")
    assert r.status_code == 403
