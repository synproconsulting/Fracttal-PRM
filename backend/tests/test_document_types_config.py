"""Tests for the configurable document_types endpoints (Sprint 9 / FPRM-144).

GET /config/document-types  — public listing of active types
POST /config/document-types — system_admin / channel_ops_admin only
PATCH /config/document-types/{id} — same permissions; code immutable

Upload endpoint validation now checks the DB table instead of the legacy enum.
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
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    DocumentTypeConfig,
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
        "sqlite:///./test_document_types_config.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_document_types_config.db"):
        try: os.remove("./test_document_types_config.db")
        except OSError: pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try: yield db
    finally: db.close()


def _seed_types(db, codes):
    """Seed only codes that don't already exist (module-scoped engine = shared state)."""
    for c in codes:
        existing = db.query(DocumentTypeConfig).filter(DocumentTypeConfig.code == c).first()
        if not existing:
            db.add(DocumentTypeConfig(id=uuid.uuid4(), code=c,
                                      label=c.replace('_', ' ').title(),
                                      is_active=True))
    db.commit()


def _unique_code(prefix="t"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_user(role):
    return User(id=uuid.uuid4(), email=f"{role.value}-{uuid.uuid4().hex[:6]}@t.com",
                hashed_password="x", role=role.value, is_active=True)


def _make_partner_user(db):
    org = PartnerOrganization(id=uuid.uuid4(), legal_name="X Corp",
                              program_type=ProgramType.distributor,
                              partner_category=PartnerCategory.reseller,
                              status=PartnerStatus.active)
    db.add(org); db.commit(); db.refresh(org)
    user = User(id=uuid.uuid4(), email=f"p-{uuid.uuid4().hex[:6]}@t.com",
                hashed_password="x", role=UserRole.partner_admin.value,
                partner_org_id=org.id, is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    return org, user


def _override_db(db):
    app.dependency_overrides[get_db] = lambda: db


def teardown_function():
    app.dependency_overrides.clear()


# -------- GET /config/document-types (public) --------


def test_list_document_types_public_returns_active_only(db_session):
    _seed_types(db_session, ["fiscal_id", "nda"])
    db_session.add(DocumentTypeConfig(id=uuid.uuid4(), code="archived_old", label="Archived", is_active=False))
    db_session.commit()
    _override_db(db_session)
    client = TestClient(app)
    r = client.get("/config/document-types")
    assert r.status_code == 200
    codes = [x["code"] for x in r.json()["items"]]
    assert "fiscal_id" in codes
    assert "nda" in codes
    assert "archived_old" not in codes


def test_list_document_types_include_inactive(db_session):
    legacy_code = _unique_code("legacy")
    db_session.add(DocumentTypeConfig(id=uuid.uuid4(), code=legacy_code, label="Legacy", is_active=False))
    db_session.commit()
    _override_db(db_session)
    client = TestClient(app)
    r = client.get("/config/document-types?include_inactive=true")
    codes = [x["code"] for x in r.json()["items"]]
    assert legacy_code in codes
    r2 = client.get("/config/document-types")
    assert legacy_code not in [x["code"] for x in r2.json()["items"]]


# -------- POST /config/document-types --------


def test_create_document_type_requires_system_admin(db_session):
    partner = _make_user(UserRole.partner_admin)
    db_session.add(partner); db_session.commit()
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: partner
    client = TestClient(app)
    r = client.post("/config/document-types", json={"code": "new_type", "label": "New Type"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 403


def test_create_document_type_system_admin_succeeds(db_session):
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    r = client.post("/config/document-types",
                    json={"code": "incorporation_cert", "label": "Incorporation Certificate"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "incorporation_cert"
    assert r.json()["is_active"] is True


def test_create_document_type_duplicate_code_409(db_session):
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    _seed_types(db_session, ["existing_code"])
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    r = client.post("/config/document-types",
                    json={"code": "existing_code", "label": "Anything"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 409


# -------- PATCH /config/document-types/{id} --------


def test_patch_document_type_updates_label(db_session):
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    row = DocumentTypeConfig(id=uuid.uuid4(), code="thing", label="Thing", is_active=True)
    db_session.add(row); db_session.commit()
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    r = client.patch(f"/config/document-types/{row.id}",
                     json={"label": "Better Thing"},
                     headers={"Authorization": "Bearer fake"})
    assert r.status_code == 200
    assert r.json()["label"] == "Better Thing"


def test_patch_document_type_can_archive(db_session):
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    row = DocumentTypeConfig(id=uuid.uuid4(), code="archive_me", label="Archive Me", is_active=True)
    db_session.add(row); db_session.commit()
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    r = client.patch(f"/config/document-types/{row.id}",
                     json={"is_active": False},
                     headers={"Authorization": "Bearer fake"})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


# -------- Upload validation uses the DB table --------


def test_upload_rejects_unknown_type_when_table_seeded(db_session):
    # Make sure at least one row exists in the config table so validation hits the DB path
    _seed_types(db_session, ["fiscal_id"])
    org, user = _make_partner_user(db_session)
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    r = client.post(f"/partners/{org.id}/documents",
                    json={"document_type": f"definitely_not_a_thing_{uuid.uuid4().hex[:6]}",
                          "document_name": "X.pdf", "file_path": "/x"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 422


def test_upload_accepts_admin_added_type_at_runtime(db_session):
    # Seed a non-enum custom type that an admin just added
    _seed_types(db_session, ["custom_admin_type"])
    org, user = _make_partner_user(db_session)
    _override_db(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    r = client.post(f"/partners/{org.id}/documents",
                    json={"document_type": "custom_admin_type",
                          "document_name": "X.pdf", "file_path": "/x"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 201, r.text
    assert r.json()["document_type"] == "custom_admin_type"
