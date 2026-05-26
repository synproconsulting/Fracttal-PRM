"""FPRM-229 — tests for GET /partners/{id}/pipeline (Sprint 14)."""
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
    PartnerOrganization,
    PartnerCategory,
    PartnerStatus,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_pipeline.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_pipeline.db"):
        try:
            os.remove("./test_pipeline.db")
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


def _make_partner(db_session) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name="Pipeline Co",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.master,
        status=PartnerStatus.active,
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_partner_admin(db_session, org_id) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"pa-{uuid.uuid4().hex[:4]}@example.com",
        hashed_password="x",
        role=UserRole.partner_admin.value,
        partner_org_id=org_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_deal(db_session, org_id, status: str, submitted_at: datetime = None) -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        status=status,
        customer_name="Cust",
        deal_name=f"D-{uuid.uuid4().hex[:4]}",
        estimated_deal_value=1000.0,
        estimated_close_date=date.today(),
        submitted_at=submitted_at,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_partner_admin_fetches_own_pipeline(client, db_session):
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    r = client.get(f"/partners/{org.id}/pipeline")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("draft", "submitted", "under_review", "approved", "rejected", "info_required"):
        assert key in body


def test_partner_admin_blocked_from_other_org(client, db_session):
    org_a = _make_partner(db_session)
    org_b = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org_a.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    r = client.get(f"/partners/{org_b.id}/pipeline")
    assert r.status_code == 403


def test_system_admin_blocked_partner_admin_only(client, db_session):
    org = _make_partner(db_session)
    admin = User(
        id=uuid.uuid4(),
        email="sa@example.com",
        hashed_password="x",
        role=UserRole.system_admin.value,
        is_active=True,
    )
    db_session.add(admin); db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin

    r = client.get(f"/partners/{org.id}/pipeline")
    assert r.status_code == 403


def test_pipeline_groups_deals_by_status(client, db_session):
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    _make_deal(db_session, org.id, "draft")
    _make_deal(db_session, org.id, "submitted", submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "approved", submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "approved", submitted_at=datetime.utcnow())

    body = client.get(f"/partners/{org.id}/pipeline").json()
    assert len(body["draft"]) == 1
    assert len(body["submitted"]) == 1
    assert len(body["approved"]) == 2
    assert len(body["rejected"]) == 0


def test_pipeline_status_filter(client, db_session):
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    _make_deal(db_session, org.id, "submitted", submitted_at=datetime.utcnow())
    _make_deal(db_session, org.id, "approved", submitted_at=datetime.utcnow())

    body = client.get(f"/partners/{org.id}/pipeline?status=approved").json()
    assert len(body["approved"]) == 1
    assert len(body["submitted"]) == 0


def test_pipeline_from_date_filter(client, db_session):
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    old = datetime.utcnow() - timedelta(days=60)
    _make_deal(db_session, org.id, "approved", submitted_at=old)
    _make_deal(db_session, org.id, "approved", submitted_at=datetime.utcnow())

    cutoff = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    body = client.get(f"/partners/{org.id}/pipeline?from_date={cutoff}").json()
    assert len(body["approved"]) == 1


def test_from_date_filter_excludes_older_deals(client, db_session):
    """PR #175: from_date excludes deals submitted strictly before the date."""
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    older = datetime(2026, 5, 10, 12, 0, 0)
    newer = datetime(2026, 5, 25, 12, 0, 0)
    _make_deal(db_session, org.id, "approved", submitted_at=older)
    _make_deal(db_session, org.id, "approved", submitted_at=newer)

    # Cutoff falls between the two -- only the newer deal qualifies.
    body = client.get(f"/partners/{org.id}/pipeline?from_date=2026-05-20").json()
    submitted_dates = [d["submitted_at"][:10] for d in body["approved"]]
    assert submitted_dates == ["2026-05-25"], submitted_dates


def test_to_date_filter_excludes_newer_deals(client, db_session):
    """PR #175: to_date is inclusive of the entire day (end-of-day cap)."""
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    older = datetime(2026, 5, 10, 12, 0, 0)
    newer = datetime(2026, 5, 25, 12, 0, 0)
    _make_deal(db_session, org.id, "approved", submitted_at=older)
    _make_deal(db_session, org.id, "approved", submitted_at=newer)

    body = client.get(f"/partners/{org.id}/pipeline?to_date=2026-05-20").json()
    submitted_dates = [d["submitted_at"][:10] for d in body["approved"]]
    assert submitted_dates == ["2026-05-10"], submitted_dates


def test_from_date_to_date_range_returns_only_matching_deals(client, db_session):
    """PR #175: combining from_date + to_date narrows to a window."""
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    earliest = datetime(2026, 5, 1, 12, 0, 0)
    middle = datetime(2026, 5, 15, 12, 0, 0)
    latest = datetime(2026, 5, 30, 12, 0, 0)
    _make_deal(db_session, org.id, "approved", submitted_at=earliest)
    _make_deal(db_session, org.id, "approved", submitted_at=middle)
    _make_deal(db_session, org.id, "approved", submitted_at=latest)

    # Window covering only the middle deal (same day both ends).
    body = client.get(
        f"/partners/{org.id}/pipeline?from_date=2026-05-15&to_date=2026-05-15"
    ).json()
    submitted_dates = [d["submitted_at"][:10] for d in body["approved"]]
    assert submitted_dates == ["2026-05-15"], submitted_dates


def test_invalid_date_format_returns_422(client, db_session):
    """PR #175: malformed date strings return 422 rather than 500/silent-pass."""
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    r = client.get(f"/partners/{org.id}/pipeline?from_date=not-a-date")
    assert r.status_code == 422

    r = client.get(f"/partners/{org.id}/pipeline?to_date=2026/05/21")
    assert r.status_code == 422


def test_pipeline_unknown_partner_returns_404(client, db_session):
    fake_id = uuid.uuid4()
    org = _make_partner(db_session)
    pa = _make_partner_admin(db_session, org.id)
    app.dependency_overrides[get_current_user] = lambda: pa

    r = client.get(f"/partners/{fake_id}/pipeline")
    assert r.status_code == 404
