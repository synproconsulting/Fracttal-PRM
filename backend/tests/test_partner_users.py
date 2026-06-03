"""Tests for partner user invite + management endpoints (FPRM-56)."""
import os
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user, hash_password
from database import Base, get_db
import models  # noqa: F401
from models import (
    AuditLog,
    InvitedRole,
    PartnerOrganization,
    PartnerUserInvite,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_partner_users.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_partner_users.db"):
        try:
            os.remove("./test_partner_users.db")
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


def make_user(role: UserRole, partner_org_id=None, email=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def make_partner() -> PartnerOrganization:
    return PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Partner {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category="master",
        status="active",
        monthly_fee_status="current",
    )


def override(db_session, user):
    def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user


def clear():
    app.dependency_overrides.clear()


def test_invite_sent_by_partner_admin(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    admin = make_user(UserRole.partner_admin, partner.id)
    db_session.add(admin)
    db_session.commit()

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/users/invite",
            json={"email": "new@test.com", "invited_role": "partner_user"},
        )
    finally:
        clear()
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "new@test.com"
    assert data["invited_role"] == "partner_user"
    assert data["token"]
    assert data["accepted_at"] is None


def test_invite_denied_for_partner_admin_other_org(db_session):
    p_a = make_partner()
    p_b = make_partner()
    db_session.add_all([p_a, p_b])
    db_session.commit()
    db_session.refresh(p_a)
    db_session.refresh(p_b)
    admin = make_user(UserRole.partner_admin, p_a.id)
    db_session.add(admin)
    db_session.commit()

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{p_b.id}/users/invite",
            json={"email": "x@test.com", "invited_role": "partner_user"},
        )
    finally:
        clear()
    assert r.status_code == 403


def test_invite_denied_for_channel_manager(db_session):
    """channel_manager doesn't have invite permission (only channel_ops_admin)."""
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()

    override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/users/invite",
            json={"email": "x@test.com", "invited_role": "partner_user"},
        )
    finally:
        clear()
    assert r.status_code == 403


def test_accept_invite_full_flow(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    inviter = make_user(UserRole.system_admin)
    db_session.add(inviter)
    db_session.commit()

    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        email="newbie@test.com",
        invited_role=InvitedRole.partner_admin,
        token=str(uuid.uuid4()),
        invited_by_user_id=inviter.id,
        expires_at=datetime.utcnow() + timedelta(hours=72),
    )
    db_session.add(invite)
    db_session.commit()
    db_session.refresh(invite)

    def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        r = client.post(
            "/auth/accept-invite",
            json={"token": invite.token, "password": "PartnerPass123!", "full_name": "Newbie X"},
        )
    finally:
        clear()
    assert r.status_code == 201, r.json()
    data = r.json()
    assert "access_token" in data
    assert data["user"]["role"] == "partner_admin"
    assert data["user"]["email"] == "newbie@test.com"
    assert data["user"]["partner_org_id"] == str(partner.id)

    db_session.expire_all()
    refreshed = db_session.query(PartnerUserInvite).filter(PartnerUserInvite.id == invite.id).first()
    assert refreshed.accepted_at is not None


def test_accept_invite_expired_rejected(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    inviter = make_user(UserRole.system_admin)
    db_session.add(inviter)
    db_session.commit()

    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        email="expired@test.com",
        invited_role=InvitedRole.partner_user,
        token=str(uuid.uuid4()),
        invited_by_user_id=inviter.id,
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(invite)
    db_session.commit()

    def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        r = client.post(
            "/auth/accept-invite",
            json={"token": invite.token, "password": "x", "full_name": "x"},
        )
    finally:
        clear()
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


def test_accept_invite_already_accepted_rejected(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    inviter = make_user(UserRole.system_admin)
    db_session.add(inviter)
    db_session.commit()

    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        email="already@test.com",
        invited_role=InvitedRole.partner_user,
        token=str(uuid.uuid4()),
        invited_by_user_id=inviter.id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        accepted_at=datetime.utcnow(),
    )
    db_session.add(invite)
    db_session.commit()

    def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        r = client.post(
            "/auth/accept-invite",
            json={"token": invite.token, "password": "x", "full_name": "x"},
        )
    finally:
        clear()
    assert r.status_code == 400


def test_accept_invite_unknown_token_404(db_session):
    def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    try:
        client = TestClient(app)
        r = client.post(
            "/auth/accept-invite",
            json={"token": "no-such-token", "password": "x", "full_name": "x"},
        )
    finally:
        clear()
    assert r.status_code == 404


def test_list_partner_users_tenant_scoped(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    member = make_user(UserRole.partner_user, partner.id)
    db_session.add(member)
    db_session.commit()
    requester = make_user(UserRole.partner_admin, partner.id)
    db_session.add(requester)
    db_session.commit()

    override(db_session, requester)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/users")
    finally:
        clear()
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["items"]]
    assert member.email in emails
    assert requester.email in emails


def test_disable_partner_user(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    target = make_user(UserRole.partner_user, partner.id)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)
    admin = make_user(UserRole.partner_admin, partner.id)
    db_session.add(admin)
    db_session.commit()

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/users/{target.id}",
            json={"is_active": False},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.object_id == target.id, AuditLog.action == "partner_user.disabled")
        .all()
    )
    assert len(entries) >= 1


def test_change_partner_user_role(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    target = make_user(UserRole.partner_user, partner.id)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)
    admin = make_user(UserRole.channel_ops_admin)
    db_session.add(admin)
    db_session.commit()

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/users/{target.id}",
            json={"role": "partner_admin"},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["role"] == "partner_admin"

    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.object_id == target.id, AuditLog.action == "partner_user.role_changed")
        .all()
    )
    assert len(entries) >= 1


def test_change_role_invalid_value_rejected(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    target = make_user(UserRole.partner_user, partner.id)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)
    admin = make_user(UserRole.channel_ops_admin)
    db_session.add(admin)
    db_session.commit()

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/users/{target.id}",
            json={"role": "system_admin"},  # not allowed for partner users
        )
    finally:
        clear()
    assert r.status_code == 422
