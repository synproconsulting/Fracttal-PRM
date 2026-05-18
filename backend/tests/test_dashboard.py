"""FPRM-179 — tests for GET /internal/dashboard/summary."""
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
    ApplicationStatus,
    DealRegistration,
    PartnerApplication,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    PartnerCategory,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_dashboard.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_dashboard.db"):
        try:
            os.remove("./test_dashboard.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        # Aggregate-count tests require a clean slate per test.
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


def _make_partner(db_session, status: PartnerStatus, legal_name: str = "Acme Co") -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.master,
        status=status,
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_application(
    db_session,
    status: ApplicationStatus,
    created_at: datetime = None,
    legal_name: str = "Bidder Co",
) -> PartnerApplication:
    app_row = PartnerApplication(
        id=uuid.uuid4(),
        applicant_email=f"a-{uuid.uuid4().hex[:4]}@example.com",
        applicant_name="A",
        legal_name=legal_name,
        status=status,
        terms_accepted=True,
    )
    if created_at:
        app_row.created_at = created_at
    db_session.add(app_row)
    db_session.commit()
    return app_row


def _make_deal(
    db_session,
    partner_org_id,
    status: str,
    estimated_value: float = 0.0,
    reviewed_at: datetime = None,
    conflict_status: str = "not_checked",
) -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status=status,
        customer_name="Some Customer",
        deal_name=f"Deal {uuid.uuid4().hex[:6]}",
        estimated_deal_value=estimated_value,
        estimated_close_date=date.today(),
        conflict_status=conflict_status,
        reviewed_at=reviewed_at,
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def test_summary_returns_zero_when_db_empty(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 200, response.text
    body = response.json()
    # User existence shouldn't affect counts on the dashboard.
    assert body["applications"]["pending_review"] == 0
    assert body["applications"]["info_required"] == 0
    assert body["applications"]["total_this_month"] == 0
    assert body["deals"]["submitted"] == 0
    assert body["deals"]["under_review"] == 0
    assert body["deals"]["approved_this_month"] == 0
    assert body["deals"]["total_pipeline_value"] == 0.0
    # The new user has no partner_org, so partners.total stays 0.
    assert body["partners"]["active"] == 0
    assert body["partners"]["pending_activation"] == 0
    assert body["partners"]["total"] == 0
    assert body["conflicts"]["open"] == 0


def test_summary_counts_applications_correctly(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    # 2 submitted, 1 in_review, 1 info_required, 1 approved
    _make_application(db_session, ApplicationStatus.submitted)
    _make_application(db_session, ApplicationStatus.submitted)
    _make_application(db_session, ApplicationStatus.in_review)
    _make_application(db_session, ApplicationStatus.info_required)
    _make_application(db_session, ApplicationStatus.approved)

    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 200
    apps = response.json()["applications"]
    assert apps["pending_review"] == 3   # 2 submitted + 1 in_review
    assert apps["info_required"] == 1
    assert apps["total_this_month"] == 5  # all created today


def test_summary_total_this_month_excludes_old_applications(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    old_date = datetime.utcnow() - timedelta(days=60)
    _make_application(db_session, ApplicationStatus.submitted, created_at=old_date)
    _make_application(db_session, ApplicationStatus.submitted)

    response = client.get("/internal/dashboard/summary")
    apps = response.json()["applications"]
    assert apps["total_this_month"] == 1  # only the new one
    assert apps["pending_review"] == 2    # both are "submitted"


def test_summary_counts_deals_and_pipeline_value(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    org = _make_partner(db_session, PartnerStatus.active)
    _make_deal(db_session, org.id, "submitted", estimated_value=10000.0)
    _make_deal(db_session, org.id, "submitted", estimated_value=5000.0)
    _make_deal(db_session, org.id, "under_review", estimated_value=7500.0)
    _make_deal(db_session, org.id, "approved", estimated_value=20000.0, reviewed_at=datetime.utcnow())
    _make_deal(db_session, org.id, "rejected", estimated_value=99999.0)  # excluded from pipeline
    _make_deal(db_session, org.id, "draft", estimated_value=42.0)        # excluded from pipeline

    deals = client.get("/internal/dashboard/summary").json()["deals"]
    assert deals["submitted"] == 2
    assert deals["under_review"] == 1
    assert deals["approved_this_month"] == 1
    # 10000 + 5000 + 7500 + 20000 = 42500 (rejected + draft excluded)
    assert deals["total_pipeline_value"] == 42500.0


def test_summary_approved_this_month_excludes_old_approvals(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    org = _make_partner(db_session, PartnerStatus.active)
    old = datetime.utcnow() - timedelta(days=60)
    _make_deal(db_session, org.id, "approved", estimated_value=1.0, reviewed_at=old)
    _make_deal(db_session, org.id, "approved", estimated_value=2.0, reviewed_at=datetime.utcnow())

    deals = client.get("/internal/dashboard/summary").json()["deals"]
    assert deals["approved_this_month"] == 1


def test_summary_counts_partners_by_status(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    _make_partner(db_session, PartnerStatus.active)
    _make_partner(db_session, PartnerStatus.active)
    _make_partner(db_session, PartnerStatus.applicant)
    _make_partner(db_session, PartnerStatus.suspended)

    partners = client.get("/internal/dashboard/summary").json()["partners"]
    assert partners["active"] == 2
    assert partners["pending_activation"] == 1
    assert partners["total"] == 4


def test_summary_counts_open_conflicts(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    org = _make_partner(db_session, PartnerStatus.active)
    _make_deal(db_session, org.id, "submitted", conflict_status="conflict_detected")
    _make_deal(db_session, org.id, "submitted", conflict_status="conflict_detected")
    _make_deal(db_session, org.id, "submitted", conflict_status="no_conflict")
    _make_deal(db_session, org.id, "submitted", conflict_status="not_checked")

    conflicts = client.get("/internal/dashboard/summary").json()["conflicts"]
    assert conflicts["open"] == 2


def test_summary_allows_channel_manager(client, db_session):
    user = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 200


def test_summary_allows_channel_ops_admin(client, db_session):
    user = _make_user(db_session, UserRole.channel_ops_admin.value)
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 200


def test_summary_rejects_sales_rep(client, db_session):
    user = _make_user(db_session, UserRole.sales_rep.value)
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 403


def test_summary_rejects_partner_admin(client, db_session):
    user = _make_user(db_session, UserRole.partner_admin.value)
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 403


def test_summary_rejects_unauthenticated(client, db_session):
    # No dependency override → real OAuth2PasswordBearer kicks in.
    response = client.get("/internal/dashboard/summary")
    assert response.status_code == 401


def test_summary_response_shape_matches_internal_home_contract(client, db_session):
    """Shape contract relied on by frontend/src/pages/InternalHome.jsx —
    every field this contract names must exist or the dashboard's KPI tiles
    will silently render '0' / '—'."""
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    body = client.get("/internal/dashboard/summary").json()
    assert set(body.keys()) == {"applications", "deals", "partners", "conflicts"}
    assert set(body["applications"].keys()) == {"pending_review", "info_required", "total_this_month"}
    assert set(body["deals"].keys()) == {"submitted", "under_review", "approved_this_month", "total_pipeline_value"}
    assert set(body["partners"].keys()) == {"active", "pending_activation", "total"}
    assert set(body["conflicts"].keys()) == {"open"}
    # Numeric types
    assert isinstance(body["deals"]["total_pipeline_value"], float)
    for k in ("pending_review", "info_required", "total_this_month"):
        assert isinstance(body["applications"][k], int)
