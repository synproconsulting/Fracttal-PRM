"""Phase 1 integration smoke test (FPRM-59).

Exercises the full auth -> RBAC -> partner data flow end-to-end:
    1. Seed system_admin (direct DB write; /auth/register only creates partner_user)
    2. Login via HTTP -> obtain JWT
    3. Create partner organization via /partners
    4. Invite a partner_admin via /partners/{id}/users/invite
    5. Accept invite (creates the partner_admin user, returns JWT)
    6. Login as partner_admin -> confirm tenant isolation on /partners/{other_id}
    7. Confirm audit log records the create + invite_sent + invite_accepted events

This uses the shared sqlite test database from conftest's session-scoped
``setup_database`` fixture. Direct seeding bypasses the public /auth/register
endpoint because it would assign role=partner_user (security: external users
cannot self-elevate to system_admin).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from main import app
from auth import hash_password
from database import Base, get_db
import models  # noqa: F401
from models import AuditLog, PartnerUserInvite, User


@pytest.fixture(scope="module")
def engine_with_overrides():
    engine = create_engine(
        "sqlite:///./test_integration_phase1.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    try:
        yield engine, SessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists("./test_integration_phase1.db"):
            try:
                os.remove("./test_integration_phase1.db")
            except OSError:
                pass


def test_phase1_full_flow(engine_with_overrides):
    engine, SessionLocal = engine_with_overrides
    client = TestClient(app)

    # ---- Step 1: seed system_admin directly (cannot register via HTTP without role param) ----
    admin_email = f"sysadmin-{uuid.uuid4().hex[:8]}@test.com"
    admin_password = "AdminPass123!"
    db = SessionLocal()
    sysadmin = User(
        id=uuid.uuid4(),
        email=admin_email,
        hashed_password=hash_password(admin_password),
        full_name="System Admin",
        role="system_admin",
        is_active=True,
        is_verified=True,
    )
    db.add(sysadmin)
    db.commit()
    sysadmin_id = str(sysadmin.id)
    db.close()

    # ---- Step 2: login via HTTP ----
    r = client.post(
        "/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    assert r.status_code == 200, r.json()
    admin_token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # ---- Step 3: create partner organization ----
    r = client.post(
        "/partners",
        json={
            "legal_name": "Integration Test Partner Corp",
            "program_type": "distributor",
            "partner_category": "master",
            "status": "active",
            "monthly_fee_status": "current",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.json()
    partner_id = r.json()["id"]
    assert r.json()["legal_name"] == "Integration Test Partner Corp"

    # ---- Step 4: invite partner_admin ----
    invite_email = f"partneradmin-{uuid.uuid4().hex[:8]}@testcorp.com"
    r = client.post(
        f"/partners/{partner_id}/users/invite",
        json={"email": invite_email, "invited_role": "partner_admin"},
        headers=headers,
    )
    assert r.status_code == 201, r.json()
    # FPRM-462 — the invite token is no longer returned in the response (it travels
    # via the email link only); read it from the DB to continue the flow.
    assert "token" not in r.json()
    assert r.json()["invited_role"] == "partner_admin"
    _db = SessionLocal()
    invite_row = (
        _db.query(PartnerUserInvite)
        .filter(PartnerUserInvite.email == invite_email)
        .first()
    )
    invite_token = invite_row.token
    _db.close()

    # ---- Step 5: accept invite ----
    r = client.post(
        "/auth/accept-invite",
        json={
            "token": invite_token,
            "password": "PartnerPass123!",
            "full_name": "Partner Admin User",
        },
    )
    assert r.status_code == 201, r.json()
    partner_token = r.json()["access_token"]
    partner_user = r.json()["user"]
    assert partner_user["role"] == "partner_admin"
    assert partner_user["partner_org_id"] == partner_id
    partner_headers = {"Authorization": f"Bearer {partner_token}"}

    # ---- Step 6a: partner_admin can see own org ----
    r = client.get(f"/partners/{partner_id}", headers=partner_headers)
    assert r.status_code == 200, r.json()
    assert r.json()["legal_name"] == "Integration Test Partner Corp"

    # ---- Step 6b: create a second org as system_admin; partner_admin must NOT see it ----
    r = client.post(
        "/partners",
        json={
            "legal_name": "Other Corp",
            "program_type": "distributor",
            "partner_category": "reseller",
            "status": "active",
            "monthly_fee_status": "current",
        },
        headers=headers,
    )
    assert r.status_code == 201
    other_id = r.json()["id"]

    r = client.get(f"/partners/{other_id}", headers=partner_headers)
    assert r.status_code == 403, "Partner admin must not access other org"

    # ---- Step 7: audit log contains expected entries ----
    r = client.get("/admin/audit-log", headers=headers)
    assert r.status_code == 200, r.json()
    actions = {entry["action"] for entry in r.json()["items"]}
    assert "partner_organization.create" in actions
    assert "partner_user.invite_sent" in actions
    assert "partner_user.invite_accepted" in actions


def test_partner_categories_public_no_auth_required(engine_with_overrides):
    """Smoke test: registration form needs partner-category list without auth."""
    engine, SessionLocal = engine_with_overrides
    client = TestClient(app)
    r = client.get("/config/partner-categories")
    assert r.status_code == 200
