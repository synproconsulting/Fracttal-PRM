"""FPRM-205 — tests for GET /internal/partners."""
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
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerChannelManager,
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


def _make_cm(db, full_name: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"cm-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name=full_name,
        role=UserRole.channel_manager.value,
        is_active=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _assign_cm(db, org, cm, assigned_at) -> PartnerChannelManager:
    row = PartnerChannelManager(
        id=uuid.uuid4(),
        partner_org_id=org.id,
        user_id=cm.id,
        assigned_at=assigned_at,
    )
    db.add(row); db.commit(); db.refresh(row)
    return row


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


# ---- FPRM-465 — Channel Manager column ---------------------------------


def _item_by_name(body, name):
    return next(i for i in body["items"] if i["legal_name"] == name)


def test_channel_manager_name_first_assigned_wins(client, db_session):
    """Two assignments on one org → the earliest-assigned CM's name is shown."""
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session, "Acme Co")
    first = _make_cm(db_session, "First Manager")
    second = _make_cm(db_session, "Second Manager")
    base = datetime(2026, 1, 1, 12, 0, 0)
    # Insert the later assignment first to prove ordering is by assigned_at,
    # not insertion order.
    _assign_cm(db_session, org, second, base + timedelta(days=5))
    _assign_cm(db_session, org, first, base)
    _caller(admin)

    r = client.get("/internal/partners")
    assert r.status_code == 200
    assert _item_by_name(r.json(), "Acme Co")["channel_manager_name"] == "First Manager"


def test_channel_manager_name_null_when_unassigned(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    _make_org(db_session, "Lonely Co")
    _caller(admin)

    r = client.get("/internal/partners")
    assert r.status_code == 200
    assert _item_by_name(r.json(), "Lonely Co")["channel_manager_name"] is None


def test_channel_manager_name_resolved_per_org_on_page(client, db_session):
    """Multi-org page: each org resolves its own first-assigned CM (no leak)."""
    admin = _make_user(db_session, UserRole.system_admin)
    org_a = _make_org(db_session, "Org A")
    org_b = _make_org(db_session, "Org B")
    _make_org(db_session, "Org C")  # unassigned
    cm_a = _make_cm(db_session, "Manager A")
    cm_b = _make_cm(db_session, "Manager B")
    base = datetime(2026, 2, 1, 9, 0, 0)
    _assign_cm(db_session, org_a, cm_a, base)
    _assign_cm(db_session, org_b, cm_b, base + timedelta(hours=1))
    _caller(admin)

    body = client.get("/internal/partners", params={"page_size": 50}).json()
    assert _item_by_name(body, "Org A")["channel_manager_name"] == "Manager A"
    assert _item_by_name(body, "Org B")["channel_manager_name"] == "Manager B"
    assert _item_by_name(body, "Org C")["channel_manager_name"] is None


def test_channel_manager_sort_puts_unassigned_last_both_directions(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org_z = _make_org(db_session, "Zeta Co")
    org_a = _make_org(db_session, "Alpha Co")
    _make_org(db_session, "Nomanager Co")  # unassigned
    cm_z = _make_cm(db_session, "Zoe Manager")
    cm_a = _make_cm(db_session, "Aaron Manager")
    base = datetime(2026, 3, 1, 9, 0, 0)
    _assign_cm(db_session, org_z, cm_z, base)
    _assign_cm(db_session, org_a, cm_a, base)
    _caller(admin)

    asc = client.get("/internal/partners", params={
        "sort_by": "channel_manager_name", "sort_dir": "asc", "page_size": 50}).json()
    names_asc = [i["channel_manager_name"] for i in asc["items"]]
    assert names_asc == ["Aaron Manager", "Zoe Manager", None]

    desc = client.get("/internal/partners", params={
        "sort_by": "channel_manager_name", "sort_dir": "desc", "page_size": 50}).json()
    names_desc = [i["channel_manager_name"] for i in desc["items"]]
    # Unassigned stays LAST even in desc (nullslast in both directions).
    assert names_desc == ["Zoe Manager", "Aaron Manager", None]


def test_channel_manager_included_in_csv_export(client, db_session):
    admin = _make_user(db_session, UserRole.system_admin)
    org = _make_org(db_session, "Csv Co")
    cm = _make_cm(db_session, "Csv Manager")
    _assign_cm(db_session, org, cm, datetime(2026, 4, 1, 9, 0, 0))
    _caller(admin)

    r = client.get("/internal/partners", params={"export": "csv"})
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert "Channel Manager" in text.splitlines()[0]
    assert "Csv Manager" in text
