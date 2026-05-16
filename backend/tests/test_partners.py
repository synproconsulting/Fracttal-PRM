"""Tests for partners router (FPRM-54)."""
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
from models import PartnerOrganization, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_partners.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_partners.db"):
        try:
            os.remove("./test_partners.db")
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


def make_user(role: UserRole, partner_org_id: uuid.UUID | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    return user


def override_dependencies(db_session, user: User):
    def _override_db():
        yield db_session

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user


def clear_overrides():
    app.dependency_overrides.clear()


def make_partner(legal_name="Acme Corp", program_type="distributor", partner_category="master"):
    return PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type=program_type,
        partner_category=partner_category,
        status="active",
        monthly_fee_status="current",
    )


def test_list_partners_as_channel_manager(db_session):
    partner = make_partner("Channel Manager Co")
    db_session.add(partner)
    db_session.commit()
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/partners")
    finally:
        clear_overrides()
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert data["total"] >= 1
    assert any(item["legal_name"] == "Channel Manager Co" for item in data["items"])


def test_list_partners_denied_for_partner_user(db_session):
    user = make_user(UserRole.partner_user, partner_org_id=uuid.uuid4())
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/partners")
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_get_partner_as_partner_admin_own_org(db_session):
    partner = make_partner("Own Org Co")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.partner_admin, partner_org_id=partner.id)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}")
    finally:
        clear_overrides()
    assert r.status_code == 200
    assert r.json()["legal_name"] == "Own Org Co"


def test_get_partner_as_partner_admin_other_org_denied(db_session):
    partner_a = make_partner("Org A")
    partner_b = make_partner("Org B")
    db_session.add_all([partner_a, partner_b])
    db_session.commit()
    db_session.refresh(partner_a)
    db_session.refresh(partner_b)
    user_a = make_user(UserRole.partner_admin, partner_org_id=partner_a.id)
    db_session.add(user_a)
    db_session.commit()
    override_dependencies(db_session, user_a)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner_b.id}")
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_get_partner_not_found(db_session):
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{uuid.uuid4()}")
    finally:
        clear_overrides()
    assert r.status_code == 404


def test_create_partner_as_system_admin(db_session):
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            "/partners",
            json={
                "legal_name": "New Partner Inc",
                "program_type": "distributor",
                "partner_category": "reseller",
                "status": "applicant",
                "monthly_fee_status": "current",
            },
        )
    finally:
        clear_overrides()
    assert r.status_code == 201
    data = r.json()
    assert data["legal_name"] == "New Partner Inc"
    assert data["partner_category"] == "reseller"


def test_create_partner_denied_for_partner_admin(db_session):
    user = make_user(UserRole.partner_admin, partner_org_id=uuid.uuid4())
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            "/partners",
            json={
                "legal_name": "X",
                "program_type": "distributor",
                "partner_category": "master",
            },
        )
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_create_partner_missing_required_fields(db_session):
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.post("/partners", json={"legal_name": ""})
    finally:
        clear_overrides()
    assert r.status_code == 422


def test_update_partner_as_channel_ops_admin(db_session):
    partner = make_partner("Original Name")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.channel_ops_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}",
            json={"dba_name": "Updated DBA", "tier": "gold"},
        )
    finally:
        clear_overrides()
    assert r.status_code == 200
    data = r.json()
    assert data["dba_name"] == "Updated DBA"
    assert data["tier"] == "gold"


def test_update_partner_as_partner_admin_own_org(db_session):
    partner = make_partner("Own Update Co")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.partner_admin, partner_org_id=partner.id)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(f"/partners/{partner.id}", json={"website": "https://example.com"})
    finally:
        clear_overrides()
    assert r.status_code == 200
    assert r.json()["website"] == "https://example.com"


def test_update_partner_as_partner_admin_other_org_denied(db_session):
    partner_a = make_partner("A Co")
    partner_b = make_partner("B Co")
    db_session.add_all([partner_a, partner_b])
    db_session.commit()
    db_session.refresh(partner_a)
    db_session.refresh(partner_b)
    user_a = make_user(UserRole.partner_admin, partner_org_id=partner_a.id)
    db_session.add(user_a)
    db_session.commit()
    override_dependencies(db_session, user_a)
    try:
        client = TestClient(app)
        r = client.patch(f"/partners/{partner_b.id}", json={"dba_name": "Hacked"})
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_update_partner_denied_for_partner_user(db_session):
    partner = make_partner("ReadOnly Co")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.partner_user, partner_org_id=partner.id)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(f"/partners/{partner.id}", json={"dba_name": "Nope"})
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_update_audit_log_entry_created(db_session):
    from models import AuditLog
    partner = make_partner("Audited Co")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.channel_ops_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.patch(f"/partners/{partner.id}", json={"dba_name": "After Audit"})
    finally:
        clear_overrides()
    assert r.status_code == 200
    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.object_id == partner.id, AuditLog.action == "partner_organization.update")
        .all()
    )
    assert len(entries) >= 1
    assert entries[-1].before_state is not None
    assert entries[-1].after_state["dba_name"] == "After Audit"


def test_create_audit_log_entry_created(db_session):
    from models import AuditLog
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()
    override_dependencies(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            "/partners",
            json={
                "legal_name": "Audit Create Co",
                "program_type": "subpartner",
                "partner_category": "promotor",
            },
        )
    finally:
        clear_overrides()
    assert r.status_code == 201
    new_id = uuid.UUID(r.json()["id"])
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "partner_organization.create", AuditLog.object_id == new_id)
        .first()
    )
    assert entry is not None
    assert entry.after_state["legal_name"] == "Audit Create Co"


def test_partner_models_importable():
    """Sanity check that all new enum types and models are importable."""
    from models import (
        PartnerOrganization,
        PartnerProfile,
        ProgramType,
        PartnerCategory,
        PartnerTier,
        PartnerStatus,
        MonthlyFeeStatus,
    )
    assert ProgramType.distributor.value == "distributor"
    assert PartnerCategory.master.value == "master"
    assert PartnerTier.gold.value == "gold"
    assert PartnerStatus.applicant.value == "applicant"
    assert MonthlyFeeStatus.current.value == "current"
    assert PartnerProfile.__tablename__ == "partner_profiles"
    assert PartnerOrganization.__tablename__ == "partner_organizations"
