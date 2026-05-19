"""FPRM-205 — tests for GET /internal/partners."""
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
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    PartnerTier,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_internal_partners.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_internal_partners.db"):
        try:
            os.remove("./test_internal_partners.db")
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


def _make_user(db, role: UserRole, *, partner_org_id=None) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
        partner_org_id=partner_org_id,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_org(db, name, *, status=PartnerStatus.active,
              category=PartnerCategory.master,
              tier=PartnerTier.silver,
              activation_complete=False) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=name,
        program_type=ProgramType.distributor,
        partner_category=category,
        tier=tier,
        status=status,
    )
    db.add(org); db.flush()
    db.add(PartnerActivationChecklist(
        id=uuid.uuid4(),
        partner_org_id=org.id,
        activation_complete=activation_complete,
    ))
    db.commit(); db.refresh(org)
    return org


def _caller(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


# ----------------------------------------------------------------------


def test_list_partners_returns_expected_fields(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session, "Acme Co", activation_complete=True)
    _caller(admin)

    r = client.get("/internal/partners")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == str(org.id)
    assert item["legal_name"] == "Acme Co"
    assert item["program_type"] == "distributor"
    assert item["partner_category"] == "master"
    assert item["tier"] == "silver"
    assert item["status"] == "active"
    assert item["activation_complete"] is True
    assert item["created_at"]


def test_list_partners_filter_by_status(client, db_session):
    admin = _make_user(db_session, UserRole.channel_manager)
    _make_org(db_session, "A", status=PartnerStatus.active)
    _make_org(db_session, "B", status=PartnerStatus.applicant)
    _make_org(db_session, "C", status=PartnerStatus.active)
    _caller(admin)

    r = client.get("/internal/partners", params={"status": "active"})
    assert r.status_code == 200
    assert r.json()["total"] == 2
    for item in r.json()["items"]:
        assert item["status"] == "active"


def test_list_partners_filter_by_category(client, db_session):
    admin = _make_user(db_session, UserRole.channel_ops_admin)
    _make_org(db_session, "M1", category=PartnerCategory.master)
    _make_org(db_session, "R1", category=PartnerCategory.reseller)
    _caller(admin)

    r = client.get("/internal/partners", params={"category": "master"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["legal_name"] == "M1"


def test_list_partners_search_case_insensitive(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _make_org(db_session, "Apple Co")
    _make_org(db_session, "Banana Inc")
    _caller(admin)

    r = client.get("/internal/partners", params={"search": "apple"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["legal_name"] == "Apple Co"

    r2 = client.get("/internal/partners", params={"search": "APPLE"})
    assert r2.status_code == 200
    assert r2.json()["total"] == 1


def test_list_partners_pagination(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    for i in range(5):
        _make_org(db_session, f"Org {i:02d}")
    _caller(admin)

    r = client.get("/internal/partners", params={"page": 2, "page_size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


def test_list_partners_invalid_status_returns_422(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _caller(admin)
    r = client.get("/internal/partners", params={"status": "garbage"})
    assert r.status_code == 422


def test_list_partners_forbidden_for_partner_admin(client, db_session):
    org = _make_org(db_session, "X")
    pa = _make_user(db_session, UserRole.partner_admin, partner_org_id=org.id)
    _caller(pa)
    r = client.get("/internal/partners")
    assert r.status_code == 403
