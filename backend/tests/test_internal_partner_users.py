"""FPRM-202 — tests for the cross-org partner-user admin endpoints."""
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
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    PartnerUserInvite,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_internal_partner_users.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_internal_partner_users.db"):
        try:
            os.remove("./test_internal_partner_users.db")
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


def _make_org(db, name="Acme Co") -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=name,
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.master,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.commit()
    return org


def _make_user(db, role: UserRole, *, partner_org_id=None, is_active=True) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name=f"{role.value} User",
        role=role.value,
        is_active=is_active,
        is_verified=True,
        partner_org_id=partner_org_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _caller(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


# -------------------- LIST --------------------


def test_list_partner_users_only_partner_roles(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session)
    _make_user(db_session, UserRole.partner_admin, partner_org_id=org.id)
    _make_user(db_session, UserRole.partner_user, partner_org_id=org.id)
    _make_user(db_session, UserRole.channel_manager)  # should NOT appear
    _caller(admin)

    r = client.get("/internal/partner-users")
    assert r.status_code == 200
    roles = {row["role"] for row in r.json()["items"]}
    assert roles <= {"partner_user", "partner_admin"}
    assert {"partner_user", "partner_admin"} == roles


def test_list_partner_users_filter_by_org(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org_a = _make_org(db_session, "Org A")
    org_b = _make_org(db_session, "Org B")
    _make_user(db_session, UserRole.partner_admin, partner_org_id=org_a.id)
    _make_user(db_session, UserRole.partner_user, partner_org_id=org_a.id)
    _make_user(db_session, UserRole.partner_admin, partner_org_id=org_b.id)
    _caller(admin)

    r = client.get("/internal/partner-users", params={"partner_org_id": str(org_a.id)})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert all(row["partner_org_id"] == str(org_a.id) for row in items)
    assert all(row["partner_org_name"] == "Org A" for row in items)


def test_list_partner_users_channel_ops_admin_allowed(client, db_session):
    coa = _make_user(db_session, UserRole.channel_ops_admin)
    org = _make_org(db_session)
    _make_user(db_session, UserRole.partner_admin, partner_org_id=org.id)
    _caller(coa)
    r = client.get("/internal/partner-users")
    assert r.status_code == 200


def test_list_partner_users_channel_manager_forbidden(client, db_session):
    cm = _make_user(db_session, UserRole.channel_manager)
    _caller(cm)
    r = client.get("/internal/partner-users")
    assert r.status_code == 403


# -------------------- ROLE CHANGE --------------------


def test_role_change_partner_user_to_admin(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session)
    target = _make_user(db_session, UserRole.partner_user, partner_org_id=org.id)
    _caller(admin)

    r = client.patch(
        f"/internal/partner-users/{target.id}/role",
        json={"role": "partner_admin"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "partner_admin"

    db_session.refresh(target)
    assert target.role == "partner_admin"

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "partner_user.role_changed",
                AuditLog.object_id == target.id)
        .first()
    )
    assert audit is not None


def test_role_change_to_internal_role_returns_422(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session)
    target = _make_user(db_session, UserRole.partner_user, partner_org_id=org.id)
    _caller(admin)

    r = client.patch(
        f"/internal/partner-users/{target.id}/role",
        json={"role": "channel_manager"},
    )
    assert r.status_code == 422


# -------------------- DISABLE / REACTIVATE --------------------


def test_disable_partner_user(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session)
    target = _make_user(db_session, UserRole.partner_admin, partner_org_id=org.id)
    _caller(admin)

    r = client.post(f"/internal/partner-users/{target.id}/disable")
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    db_session.refresh(target)
    assert target.is_active is False


def test_reactivate_partner_user(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session)
    target = _make_user(db_session, UserRole.partner_user, partner_org_id=org.id, is_active=False)
    _caller(admin)

    r = client.post(f"/internal/partner-users/{target.id}/reactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True
    db_session.refresh(target)
    assert target.is_active is True


# -------------------- INVITE --------------------


def test_invite_to_partner_org(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session, "Invitee Co")
    _caller(admin)

    r = client.post(
        "/internal/partner-users/invite",
        json={
            "email": "new.partner@example.com",
            "partner_org_id": str(org.id),
            "invited_role": "partner_admin",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "new.partner@example.com"
    assert body["invited_role"] == "partner_admin"
    assert body["partner_org_id"] == str(org.id)
    assert body["token"]

    invite = (
        db_session.query(PartnerUserInvite)
        .filter(PartnerUserInvite.email == "new.partner@example.com")
        .first()
    )
    assert invite is not None
    assert str(invite.partner_org_id) == str(org.id)


def test_invite_with_unknown_org_returns_404(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _caller(admin)

    r = client.post(
        "/internal/partner-users/invite",
        json={
            "email": "x@y.com",
            "partner_org_id": str(uuid.uuid4()),
            "invited_role": "partner_user",
        },
    )
    assert r.status_code == 404


# -------------------- 403 SWEEP --------------------


def test_all_endpoints_forbidden_for_channel_manager(client, db_session):
    cm = _make_user(db_session, UserRole.channel_manager)
    org = _make_org(db_session)
    target = _make_user(db_session, UserRole.partner_user, partner_org_id=org.id)
    _caller(cm)

    assert client.get("/internal/partner-users").status_code == 403
    assert client.patch(
        f"/internal/partner-users/{target.id}/role",
        json={"role": "partner_admin"},
    ).status_code == 403
    assert client.post(f"/internal/partner-users/{target.id}/disable").status_code == 403
    assert client.post(f"/internal/partner-users/{target.id}/reactivate").status_code == 403
    assert client.post(
        "/internal/partner-users/invite",
        json={"email": "x@y.com", "partner_org_id": str(org.id), "invited_role": "partner_user"},
    ).status_code == 403
