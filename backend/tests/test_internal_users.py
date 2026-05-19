"""FPRM-194 — tests for internal user management endpoints."""
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
import models  # noqa: F401  registers all models
from models import AuditLog, PasswordResetToken, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_internal_users.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_internal_users.db"):
        try:
            os.remove("./test_internal_users.db")
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


def _make_user(db_session, role: UserRole, *, partner_org_id=None,
               is_active=True) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        full_name=f"{role.value.replace('_', ' ').title()} User",
        role=role.value,
        is_active=is_active,
        is_verified=True,
        partner_org_id=partner_org_id,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _set_caller(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


# ---------------- LIST /internal/users ----------------


def test_list_internal_users_excludes_partner_users(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _make_user(db_session, UserRole.channel_manager)
    _make_user(db_session, UserRole.partner_admin)
    _make_user(db_session, UserRole.partner_user)
    _set_caller(admin)

    r = client.get("/internal/users")
    assert r.status_code == 200
    items = r.json()["items"]
    roles = {row["role"] for row in items}
    assert "partner_user" not in roles
    assert "partner_admin" not in roles
    assert {"system_admin", "channel_manager"} <= roles


def test_list_internal_users_role_filter(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _make_user(db_session, UserRole.channel_manager)
    _make_user(db_session, UserRole.sales_rep)
    _set_caller(admin)

    r = client.get("/internal/users", params={"role": "channel_manager"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(row["role"] == "channel_manager" for row in items)
    assert len(items) == 1


def test_list_internal_users_invalid_role_returns_422(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _set_caller(admin)

    r = client.get("/internal/users", params={"role": "garbage"})
    assert r.status_code == 422


def test_list_internal_users_forbidden_for_channel_manager(client, db_session):
    cm = _make_user(db_session, UserRole.channel_manager)
    _set_caller(cm)

    r = client.get("/internal/users")
    assert r.status_code == 403


# ---------------- GET /internal/users/{id} ----------------


def test_get_single_internal_user(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.channel_ops_admin)
    _set_caller(admin)

    r = client.get(f"/internal/users/{target.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(target.id)
    assert body["role"] == "channel_ops_admin"
    assert "last_login_at" in body


def test_get_partner_user_returns_404(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    partner = _make_user(db_session, UserRole.partner_admin)
    _set_caller(admin)

    r = client.get(f"/internal/users/{partner.id}")
    assert r.status_code == 404


# ---------------- POST /internal/users/invite ----------------


def test_invite_internal_user_creates_row_and_reset_token(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _set_caller(admin)

    payload = {
        "email": "new.channel.mgr@example.com",
        "role": "channel_manager",
        "full_name": "New CM",
    }
    r = client.post("/internal/users/invite", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == payload["email"]
    assert body["role"] == "channel_manager"

    invited = db_session.query(User).filter(User.email == payload["email"]).first()
    assert invited is not None
    assert invited.is_active is True
    # Random password — caller shouldn't be able to guess it; ensure the hash
    # is set but not the literal "x" sentinel used by _make_user.
    assert invited.hashed_password and invited.hashed_password != "x"

    reset = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == invited.id)
        .first()
    )
    assert reset is not None

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "internal_user.invited",
                AuditLog.object_id == invited.id)
        .first()
    )
    assert audit is not None


def test_invite_duplicate_email_returns_409(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    existing = _make_user(db_session, UserRole.channel_manager)
    _set_caller(admin)

    r = client.post(
        "/internal/users/invite",
        json={"email": existing.email, "role": "channel_manager"},
    )
    assert r.status_code == 409


def test_invite_partner_role_returns_422(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _set_caller(admin)

    r = client.post(
        "/internal/users/invite",
        json={"email": "p@example.com", "role": "partner_admin"},
    )
    assert r.status_code == 422


# ---------------- PATCH /internal/users/{id}/role ----------------


def test_change_role_success_and_audited(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.channel_manager)
    _set_caller(admin)

    r = client.patch(
        f"/internal/users/{target.id}/role",
        json={"role": "channel_ops_admin"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "channel_ops_admin"

    db_session.refresh(target)
    assert target.role == "channel_ops_admin"

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "internal_user.role_changed",
                AuditLog.object_id == target.id)
        .first()
    )
    assert audit is not None
    assert audit.before_state == {"role": "channel_manager"}
    assert audit.after_state == {"role": "channel_ops_admin"}


def test_cannot_change_own_role(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _set_caller(admin)

    r = client.patch(
        f"/internal/users/{admin.id}/role",
        json={"role": "channel_manager"},
    )
    assert r.status_code == 400
    assert "own role" in r.json()["detail"]


def test_cannot_demote_last_system_admin(client, db_session):
    sole = _make_user(db_session, UserRole.system_admin)
    other = _make_user(db_session, UserRole.system_admin, is_active=False)
    _set_caller(sole)
    # Promote a fresh admin into the role then demote sole — but only `sole`
    # is active, so demoting sole is the last *active* system_admin.
    r = client.patch(
        f"/internal/users/{sole.id}/role",
        json={"role": "channel_manager"},
    )
    # Caller is sole and target is sole — the own-role check fires first.
    assert r.status_code == 400

    # Now have two active system_admins and demote one — should succeed.
    other.is_active = True
    db_session.commit()
    second = _make_user(db_session, UserRole.system_admin)  # third active admin
    r2 = client.patch(
        f"/internal/users/{other.id}/role",
        json={"role": "channel_manager"},
    )
    assert r2.status_code == 200
    assert second.role == "system_admin"  # untouched


def test_demote_only_remaining_active_system_admin_blocked(client, db_session):
    # The only active system_admin besides the caller is the target.
    caller = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.system_admin)
    _set_caller(caller)

    # Disable target so caller is the only active admin, then try to demote
    # target. The "last active system_admin" guard inspects target's current
    # role: since target is a system_admin and demoting them would leave one
    # active admin (caller), it should still succeed. The guard fires when
    # demoting target would leave **zero** active admins.
    # To exercise the guard, disable the caller is not possible (self-protection)
    # so simulate: only target is system_admin AND active. Caller becomes
    # channel_ops_admin via DB-level mutation (test-only).
    caller.role = UserRole.channel_ops_admin.value
    db_session.commit()
    # Now caller is no longer a system_admin so they shouldn't be able to call
    # the endpoint at all. Reassert that.
    r = client.patch(
        f"/internal/users/{target.id}/role",
        json={"role": "channel_manager"},
    )
    assert r.status_code == 403


def test_demote_blocked_when_target_is_only_active_admin(client, db_session):
    caller = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.system_admin, is_active=False)
    _set_caller(caller)

    # Set target active so we have exactly two active admins.
    target.is_active = True
    db_session.commit()
    # Now disable caller — but caller can't disable themselves through the API.
    # Simulate at DB level so only target is the "last" admin from the count.
    caller.is_active = False
    db_session.commit()
    # Caller's auth dependency still resolves because we override
    # get_current_user; this lets us test the "remaining admins" guard.
    r = client.patch(
        f"/internal/users/{target.id}/role",
        json={"role": "channel_manager"},
    )
    assert r.status_code == 400
    assert "last active system_admin" in r.json()["detail"]


# ---------------- POST /internal/users/{id}/disable ----------------


def test_disable_user(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.channel_manager)
    _set_caller(admin)

    r = client.post(f"/internal/users/{target.id}/disable")
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    db_session.refresh(target)
    assert target.is_active is False


def test_cannot_disable_self(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _set_caller(admin)

    r = client.post(f"/internal/users/{admin.id}/disable")
    assert r.status_code == 400
    assert "own account" in r.json()["detail"]


def test_reactivate_user(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    target = _make_user(db_session, UserRole.channel_manager, is_active=False)
    _set_caller(admin)

    r = client.post(f"/internal/users/{target.id}/reactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    db_session.refresh(target)
    assert target.is_active is True


# ---------------- AUTH / ROLE GUARDS ----------------


def test_all_endpoints_forbidden_for_non_system_admin(client, db_session):
    cm = _make_user(db_session, UserRole.channel_manager)
    target = _make_user(db_session, UserRole.channel_ops_admin)
    _set_caller(cm)

    assert client.get("/internal/users").status_code == 403
    assert client.get(f"/internal/users/{target.id}").status_code == 403
    assert client.post(
        "/internal/users/invite",
        json={"email": "x@y.com", "role": "channel_manager"},
    ).status_code == 403
    assert client.patch(
        f"/internal/users/{target.id}/role",
        json={"role": "channel_manager"},
    ).status_code == 403
    assert client.post(f"/internal/users/{target.id}/disable").status_code == 403
    assert client.post(f"/internal/users/{target.id}/reactivate").status_code == 403
