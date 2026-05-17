"""FPRM-119 regression: JWT payload and /auth/me must include partner_org_id.

The partner portal frontend decodes the JWT to resolve the user's partner_org_id
on every page load. Forgetting to include it (Sprint 6 default) left
PartnerPortalLayout unable to fetch the org without an extra round-trip.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import decode_access_token, hash_password
from database import Base, get_db
import models  # noqa: F401  registers all models
from models import PartnerOrganization, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_auth_partner_org_id.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_auth_partner_org_id.db"):
        try:
            os.remove("./test_auth_partner_org_id.db")
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


def _override_db(db_session):
    def _db_dep():
        yield db_session

    app.dependency_overrides[get_db] = _db_dep


def _make_partner(db, legal_name="Org X"):
    partner = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type="distributor",
        partner_category="reseller",
        status="active",
        monthly_fee_status="current",
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def _make_user(db, role, partner_org_id=None, password="TestPass123!"):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=hash_password(password),
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_jwt_includes_partner_org_id(db_session):
    partner = _make_partner(db_session, "JWT Login Co")
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/auth/login", json={"email": user.email, "password": "TestPass123!"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    payload = decode_access_token(r.json()["access_token"])
    assert payload["partner_org_id"] == str(partner.id)
    assert payload["role"] == "partner_admin"


def test_login_jwt_partner_org_id_null_for_internal_users(db_session):
    user = _make_user(db_session, UserRole.system_admin)
    _override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/auth/login", json={"email": user.email, "password": "TestPass123!"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    payload = decode_access_token(r.json()["access_token"])
    assert payload["partner_org_id"] is None


def test_me_response_includes_partner_org_id(db_session):
    partner = _make_partner(db_session, "Me Co")
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override_db(db_session)
    try:
        client = TestClient(app)
        login_r = client.post(
            "/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        token = login_r.json()["access_token"]
        me_r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()
    assert me_r.status_code == 200
    body = me_r.json()
    assert body["partner_org_id"] == str(partner.id)
    assert body["email"] == user.email


def test_me_response_partner_org_id_null_for_internal(db_session):
    user = _make_user(db_session, UserRole.channel_ops_admin)
    _override_db(db_session)
    try:
        client = TestClient(app)
        login_r = client.post(
            "/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        token = login_r.json()["access_token"]
        me_r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()
    assert me_r.status_code == 200
    assert me_r.json()["partner_org_id"] is None
