"""FPRM-186 — tests for cancel-info-request on applications and deals."""
import os
import sys
import uuid
from datetime import date, datetime

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
    AuditLog,
    DealMessage,
    DealRegistration,
    PartnerApplication,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_cancel_info_request.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_cancel_info_request.db"):
        try:
            os.remove("./test_cancel_info_request.db")
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


def _make_user(db_session, role: str, partner_org_id=None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name="U",
        role=role,
        is_active=True,
        partner_org_id=partner_org_id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_org(db_session) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name="Acme",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.master,
        status=PartnerStatus.active,
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_application(db_session, status: ApplicationStatus, info_message: str = None) -> PartnerApplication:
    # info_request_message is not a real column on PartnerApplication — it's
    # only ever set as an in-memory attribute by the request-info endpoint and
    # returned in the response (never persisted). The cancel endpoint clears
    # it via the same in-memory pattern, so we don't seed it on the row.
    app_row = PartnerApplication(
        id=uuid.uuid4(),
        applicant_email="a@example.com",
        applicant_name="A",
        legal_name="A Co",
        status=status,
        terms_accepted=True,
    )
    if info_message is not None:
        app_row.info_request_message = info_message
    db_session.add(app_row)
    db_session.commit()
    return app_row


def _make_deal(db_session, partner_org_id, status: str = "info_required") -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status=status,
        customer_name="C",
        deal_name=f"D {uuid.uuid4().hex[:4]}",
        estimated_close_date=date.today(),
    )
    db_session.add(deal)
    db_session.commit()
    return deal


# ---------- application cancel-info-request ----------


def test_cancel_info_request_app_success(client, db_session):
    app_row = _make_application(db_session, ApplicationStatus.info_required, info_message="Please send X")
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "under_review"
    assert body["info_request_message"] is None

    # Verify DB state — only the status transition is persisted
    # (info_request_message is in-memory only — see _make_application note).
    db_session.expire_all()
    fresh = db_session.query(PartnerApplication).filter(PartnerApplication.id == app_row.id).first()
    assert fresh.status == ApplicationStatus.under_review

    # Verify audit
    entries = db_session.query(AuditLog).filter(AuditLog.object_id == app_row.id).all()
    actions = [e.action for e in entries]
    assert "partner_application.info_request_cancelled" in actions


def test_cancel_info_request_app_wrong_status_400(client, db_session):
    app_row = _make_application(db_session, ApplicationStatus.submitted)
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 400
    assert "not in info_required status" in response.json()["detail"]


def test_cancel_info_request_app_unknown_404(client, db_session):
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/applications/{uuid.uuid4()}/cancel-info-request")
    assert response.status_code == 404


def test_cancel_info_request_app_403_for_partner_role(client, db_session):
    app_row = _make_application(db_session, ApplicationStatus.info_required)
    org = _make_org(db_session)
    user = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 403


def test_cancel_info_request_app_403_for_sales_rep(client, db_session):
    """sales_rep does not have partner_application:read_all, so the
    require_permission dependency rejects with 403 before _require_review_role
    even gets called."""
    app_row = _make_application(db_session, ApplicationStatus.info_required)
    user = _make_user(db_session, UserRole.sales_rep.value)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 403


def test_cancel_info_request_app_allows_channel_ops_admin(client, db_session):
    app_row = _make_application(db_session, ApplicationStatus.info_required)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 200


def test_cancel_info_request_app_allows_system_admin(client, db_session):
    app_row = _make_application(db_session, ApplicationStatus.info_required)
    reviewer = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/applications/{app_row.id}/cancel-info-request")
    assert response.status_code == 200


# ---------- deal cancel-info-request ----------


def test_cancel_info_request_deal_success(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="info_required")
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/internal/deals/{deal.id}/cancel-info-request")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "under_review"

    # System message posted on the thread
    msgs = db_session.query(DealMessage).filter(DealMessage.deal_id == deal.id).all()
    assert any("Info request cancelled" in (m.message or "") for m in msgs)

    # Audit entry
    actions = [
        e.action for e in
        db_session.query(AuditLog).filter(AuditLog.object_id == deal.id).all()
    ]
    assert "deal_registration.info_request_cancelled" in actions


def test_cancel_info_request_deal_wrong_status_400(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="under_review")
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/internal/deals/{deal.id}/cancel-info-request")
    assert response.status_code == 400
    assert "not in info_required status" in response.json()["detail"]


def test_cancel_info_request_deal_unknown_404(client, db_session):
    reviewer = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/internal/deals/{uuid.uuid4()}/cancel-info-request")
    assert response.status_code == 404


def test_cancel_info_request_deal_403_for_partner_role(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    user = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(f"/internal/deals/{deal.id}/cancel-info-request")
    assert response.status_code == 403


def test_cancel_info_request_deal_403_for_sales_rep(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    user = _make_user(db_session, UserRole.sales_rep.value)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(f"/internal/deals/{deal.id}/cancel-info-request")
    assert response.status_code == 403


def test_cancel_info_request_deal_allows_channel_ops_admin(client, db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin.value)
    app.dependency_overrides[get_current_user] = lambda: reviewer

    response = client.post(f"/internal/deals/{deal.id}/cancel-info-request")
    assert response.status_code == 200
