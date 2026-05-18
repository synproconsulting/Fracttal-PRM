"""Tests for deal collaboration thread + request-info (Sprint 9 / FPRM-139)."""
import os
import sys
import uuid

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
    AuditLog,
    DealMessage,
    DealRegistration,
    PartnerActivationChecklist,
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
        "sqlite:///./test_deal_messages.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_deal_messages.db"):
        try:
            os.remove("./test_deal_messages.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _make_user(role: UserRole, partner_org_id=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def _make_org(db) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_active_checklist(db, org_id):
    cl = PartnerActivationChecklist(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        profile_complete=True,
        documents_uploaded=True,
        terms_signed=True,
        activation_complete=True,
    )
    db.add(cl)
    db.commit()
    return cl


def _make_deal(db, org_id, *, status="submitted") -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        status=status,
        customer_name="ACME Corp",
        deal_name="Deal X",
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def _client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


# -------- GET /deal-registrations/{id}/messages --------


def test_list_messages_returns_chronological_order(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    # Seed two messages
    m1 = DealMessage(id=uuid.uuid4(), deal_id=deal.id, sender_type="partner",
                     sender_id=partner.id, sender_email=partner.email, message="First")
    m2 = DealMessage(id=uuid.uuid4(), deal_id=deal.id, sender_type="internal",
                     sender_id=None, sender_email="reviewer@test.com", message="Second")
    db_session.add(m1); db_session.commit()
    db_session.add(m2); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.get(f"/deal-registrations/{deal.id}/messages")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["message"] == "First"
    assert body[1]["message"] == "Second"


def test_list_messages_partner_admin_forbidden_on_other_org(db_session):
    org1 = _make_org(db_session)
    org2 = _make_org(db_session)
    deal = _make_deal(db_session, org1.id)
    other_partner = _make_user(UserRole.partner_admin, org2.id)
    db_session.add(other_partner); db_session.commit()

    client = next(_client_for(db_session, other_partner))
    r = client.get(f"/deal-registrations/{deal.id}/messages")
    assert r.status_code == 403


def test_list_messages_404_unknown_deal(db_session):
    org = _make_org(db_session)
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.get(f"/deal-registrations/{uuid.uuid4()}/messages")
    assert r.status_code == 404


# -------- POST /deal-registrations/{id}/messages --------


def test_post_message_as_partner_records_partner_sender(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.post(f"/deal-registrations/{deal.id}/messages",
                    json={"message": "Customer address: 123 Main"})
    assert r.status_code == 201
    body = r.json()
    assert body["sender_type"] == "partner"
    assert body["sender_email"] == partner.email
    assert body["message"] == "Customer address: 123 Main"

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "deal_registration.message_posted")
        .filter(AuditLog.object_id == deal.id)
        .first()
    )
    assert audit is not None


def test_post_message_as_channel_manager_records_internal_sender(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = next(_client_for(db_session, reviewer))
    r = client.post(f"/deal-registrations/{deal.id}/messages",
                    json={"message": "Looking at this now"})
    assert r.status_code == 201
    assert r.json()["sender_type"] == "internal"


def test_post_message_partner_admin_forbidden_on_other_org(db_session):
    org1 = _make_org(db_session)
    org2 = _make_org(db_session)
    deal = _make_deal(db_session, org1.id)
    other_partner = _make_user(UserRole.partner_admin, org2.id)
    db_session.add(other_partner); db_session.commit()

    client = next(_client_for(db_session, other_partner))
    r = client.post(f"/deal-registrations/{deal.id}/messages",
                    json={"message": "hi"})
    assert r.status_code == 403


def test_post_message_empty_returns_422(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id)
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.post(f"/deal-registrations/{deal.id}/messages",
                    json={"message": "   "})
    assert r.status_code == 422


# -------- POST /internal/deals/{id}/request-info --------


def test_request_info_transitions_under_review_to_info_required(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="under_review")
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = next(_client_for(db_session, reviewer))
    r = client.post(f"/internal/deals/{deal.id}/request-info",
                    json={"message": "Need customer address"})
    assert r.status_code == 200
    assert r.json()["status"] == "info_required"

    # Confirm message was posted to the thread
    msgs = db_session.query(DealMessage).filter(DealMessage.deal_id == deal.id).all()
    assert len(msgs) == 1
    assert msgs[0].sender_type == "internal"
    assert msgs[0].message == "Need customer address"


def test_request_info_400_on_wrong_status(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="submitted")
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = next(_client_for(db_session, reviewer))
    r = client.post(f"/internal/deals/{deal.id}/request-info",
                    json={"message": "anything"})
    assert r.status_code == 400


def test_request_info_requires_message(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="under_review")
    reviewer = _make_user(UserRole.channel_manager)
    db_session.add(reviewer); db_session.commit()

    client = next(_client_for(db_session, reviewer))
    r = client.post(f"/internal/deals/{deal.id}/request-info",
                    json={"message": ""})
    assert r.status_code == 422


def test_request_info_partner_admin_403(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="under_review")
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.post(f"/internal/deals/{deal.id}/request-info",
                    json={"message": "x"})
    assert r.status_code == 403


# -------- info_required PATCH + resubmit --------


def test_partner_admin_can_resubmit_from_info_required(db_session):
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="info_required")
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.post(f"/deal-registrations/{deal.id}/submit")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"


def test_patch_blocked_when_status_is_info_required(db_session):
    """PATCH is draft-only per existing router rules; info_required must use
    submit instead. Documenting current behaviour."""
    org = _make_org(db_session)
    deal = _make_deal(db_session, org.id, status="info_required")
    partner = _make_user(UserRole.partner_admin, org.id)
    db_session.add(partner); db_session.commit()

    client = next(_client_for(db_session, partner))
    r = client.patch(f"/deal-registrations/{deal.id}",
                     json={"deal_notes": "new info"})
    assert r.status_code == 400
