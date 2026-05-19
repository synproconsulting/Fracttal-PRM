"""FPRM-208 — tests for PATCH /internal/partners/{id}/status."""
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
        "sqlite:///./test_partner_status.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_partner_status.db"):
        try:
            os.remove("./test_partner_status.db")
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


def _make_user(db, role: UserRole) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_org(db, *, status=PartnerStatus.active) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name="Test Partner Org",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=status,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def test_suspend_partner_org_as_system_admin(client, db_session):
    org = _make_org(db_session, status=PartnerStatus.active)
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "suspended"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "suspended"


def test_reactivate_partner_org(client, db_session):
    org = _make_org(db_session, status=PartnerStatus.suspended)
    _as_user(_make_user(db_session, UserRole.channel_ops_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "active"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"


def test_invalid_status_value(client, db_session):
    org = _make_org(db_session)
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "banana"})
    assert r.status_code == 400, r.text


def test_cannot_set_applicant_status(client, db_session):
    org = _make_org(db_session, status=PartnerStatus.active)
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "applicant"})
    assert r.status_code == 400, r.text


def test_wrong_role_forbidden(client, db_session):
    org = _make_org(db_session)
    _as_user(_make_user(db_session, UserRole.channel_manager))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "suspended"})
    assert r.status_code == 403, r.text


def test_partner_role_forbidden(client, db_session):
    org = _make_org(db_session)
    _as_user(_make_user(db_session, UserRole.partner_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "suspended"})
    assert r.status_code == 403, r.text


def test_missing_status_returns_400(client, db_session):
    org = _make_org(db_session)
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={})
    assert r.status_code == 400, r.text


def test_unknown_partner_returns_404(client, db_session):
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(
        f"/internal/partners/{uuid.uuid4()}/status",
        json={"status": "suspended"},
    )
    assert r.status_code == 404, r.text


def test_terminate_partner_org(client, db_session):
    org = _make_org(db_session, status=PartnerStatus.active)
    _as_user(_make_user(db_session, UserRole.system_admin))

    r = client.patch(f"/internal/partners/{org.id}/status", json={"status": "terminated"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "terminated"
