"""Tests for backend/provisioning.py (FPRM-92 + FPRM-107 checklist row)."""
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
    ApplicationStatus,
    InvitedRole,
    PartnerActivationChecklist,
    PartnerApplication,
    PartnerCategory,
    PartnerOrganization,
    PartnerProfile,
    PartnerUserInvite,
    User,
)
from roles import UserRole
from provisioning import provision_partner_from_application


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_provisioning.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_provisioning.db"):
        try:
            os.remove("./test_provisioning.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
    )


def make_submitted_application(db_session, **kwargs) -> PartnerApplication:
    defaults = dict(
        applicant_email=f"applicant-{uuid.uuid4().hex[:6]}@acme.test",
        applicant_name="Founder",
        legal_name="Acme Inc",
        dba_name="Acme",
        website="https://acme.test",
        phone="+1-555-0100",
        requested_categories=["master"],
        territory=["US"],
        industries=["manufacturing"],
        year_established=2010,
        employee_count=50,
        annual_revenue="10-25M",
        cmms_experience=True,
        cmms_experience_description="5 years",
        partnership_goals="Grow share in US",
        additional_info="-",
        terms_accepted=True,
        status=ApplicationStatus.submitted,
    )
    defaults.update(kwargs)
    a = PartnerApplication(id=uuid.uuid4(), **defaults)
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


# ---------------- provisioning unit tests ----------------


def test_provisioning_creates_partner_org(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)

    org = db_session.query(PartnerOrganization).filter_by(id=result["partner_org_id"]).first()
    assert org is not None
    assert org.legal_name == "Acme Inc"
    assert org.partner_category == PartnerCategory.master
    assert org.email == app_record.applicant_email


def test_provisioning_creates_partner_profile(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    profile = (
        db_session.query(PartnerProfile)
        .filter_by(partner_org_id=result["partner_org_id"])
        .first()
    )
    assert profile is not None
    assert profile.year_established == 2010
    assert profile.partnership_goals == "Grow share in US"


def test_provisioning_creates_invite(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    invite = (
        db_session.query(PartnerUserInvite)
        .filter_by(partner_org_id=result["partner_org_id"])
        .first()
    )
    assert invite is not None
    assert invite.email == app_record.applicant_email
    assert invite.invited_role == InvitedRole.partner_admin
    assert invite.token == result["invite_token"]
    assert invite.invited_by_user_id == reviewer.id


def test_provisioning_creates_activation_checklist(db_session):
    """FPRM-107 / Sprint 7 — new partners get an all-False checklist row."""
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    checklist = (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=result["partner_org_id"])
        .first()
    )
    assert checklist is not None
    assert checklist.profile_complete is False
    assert checklist.documents_uploaded is False
    assert checklist.terms_signed is False
    assert checklist.baseline_training_complete is False
    assert checklist.activation_complete is False
    assert checklist.activated_at is None


def test_provisioning_links_application_to_org(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    db_session.refresh(app_record)
    assert app_record.partner_org_id == result["partner_org_id"]
    assert app_record.reviewer_id == reviewer.id
    assert app_record.reviewed_at is not None


def test_provisioning_falls_back_to_reseller_when_category_unknown(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session, requested_categories=["unknown_tier"])

    result = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    org = db_session.query(PartnerOrganization).filter_by(id=result["partner_org_id"]).first()
    assert org.partner_category == PartnerCategory.reseller


def test_provisioning_is_idempotent(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    app_record = make_submitted_application(db_session)

    first = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    second = provision_partner_from_application(db_session, app_record.id, reviewer.id)
    assert first["partner_org_id"] == second["partner_org_id"]
    assert second["already_provisioned"] is True
    orgs = db_session.query(PartnerOrganization).filter_by(id=first["partner_org_id"]).all()
    assert len(orgs) == 1


# ---------------- approve endpoint triggers provisioning ----------------


def _create_and_submit(client):
    r = client.post(
        "/applications",
        json={"applicant_email": f"approve-{uuid.uuid4().hex[:6]}@acme.test"},
    )
    body = r.json()
    app_id, token = body["id"], body["draft_token"]
    client.patch(
        f"/applications/{app_id}?draft_token={token}",
        json={"applicant_name": "Founder", "legal_name": "Acme Inc", "terms_accepted": True},
    )
    client.post(f"/applications/{app_id}/submit?draft_token={token}")
    return app_id


def test_approve_endpoint_triggers_provisioning(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    def _db_only():
        yield db_session
    app.dependency_overrides[get_db] = _db_only
    try:
        client = TestClient(app)
        app_id = _create_and_submit(client)
    finally:
        app.dependency_overrides.clear()

    def _user():
        return reviewer
    app.dependency_overrides[get_db] = _db_only
    app.dependency_overrides[get_current_user] = _user
    try:
        r = client.post(f"/applications/{app_id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text

    app_record = db_session.query(PartnerApplication).filter_by(id=uuid.UUID(app_id)).first()
    assert app_record.partner_org_id is not None
    org = db_session.query(PartnerOrganization).filter_by(id=app_record.partner_org_id).first()
    assert org is not None
    invite = db_session.query(PartnerUserInvite).filter_by(partner_org_id=org.id).first()
    assert invite is not None
    # FPRM-107: approve flow must create the activation checklist too.
    checklist = (
        db_session.query(PartnerActivationChecklist).filter_by(partner_org_id=org.id).first()
    )
    assert checklist is not None
    assert checklist.activation_complete is False
