"""Tests for the partner_applications router (FPRM-75)."""
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
from models import User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_applications.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_applications.db"):
        try:
            os.remove("./test_applications.db")
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


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
    )


def override_db(db_session):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db


def override_internal_user(db_session, user: User):
    def _override_db():
        yield db_session

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user


def clear_overrides():
    app.dependency_overrides.clear()


# ---------------- POST /applications ----------------

def test_create_draft_returns_id_and_token(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "founder@acme.test"})
    finally:
        clear_overrides()
    assert r.status_code == 201
    body = r.json()
    assert "id" in body
    assert "draft_token" in body
    assert len(body["draft_token"]) >= 16


def test_create_draft_requires_applicant_email(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={})
    finally:
        clear_overrides()
    assert r.status_code == 422


# ---------------- PATCH /applications/{id} ----------------

def test_patch_updates_fields_with_valid_draft_token(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "patch@acme.test"})
        body = r.json()
        app_id, token = body["id"], body["draft_token"]

        r2 = client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"legal_name": "Acme Inc", "year_established": 2010},
        )
    finally:
        clear_overrides()
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["legal_name"] == "Acme Inc"
    assert data["year_established"] == 2010


# ---------------- FPRM-464 — empty-string coercion on numeric fields ----------------

def test_patch_year_established_empty_string_coerced_to_null(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        body = client.post(
            "/applications", json={"applicant_email": "coerce-empty@acme.test"}
        ).json()
        app_id, token = body["id"], body["draft_token"]

        r = client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"year_established": "", "employee_count": ""},
        )
        assert r.status_code == 200, r.text
        assert r.json()["year_established"] is None
        assert r.json()["employee_count"] is None

        row = (
            db_session.query(models.PartnerApplication)
            .filter(models.PartnerApplication.id == uuid.UUID(app_id))
            .first()
        )
        assert row.year_established is None
        assert row.employee_count is None
    finally:
        clear_overrides()


def test_patch_year_established_integer_preserved(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        body = client.post(
            "/applications", json={"applicant_email": "coerce-int@acme.test"}
        ).json()
        app_id, token = body["id"], body["draft_token"]

        r = client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"year_established": 2020},
        )
        assert r.status_code == 200, r.text
        assert r.json()["year_established"] == 2020
    finally:
        clear_overrides()


def test_patch_year_established_null_stays_null(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        body = client.post(
            "/applications", json={"applicant_email": "coerce-null@acme.test"}
        ).json()
        app_id, token = body["id"], body["draft_token"]

        r = client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"year_established": None},
        )
        assert r.status_code == 200, r.text
        assert r.json()["year_established"] is None
    finally:
        clear_overrides()


def test_create_draft_empty_numeric_coerced_to_null(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post(
            "/applications",
            json={"applicant_email": "create-coerce@acme.test", "year_established": ""},
        )
        assert r.status_code == 201, r.text
        app_id = r.json()["id"]
        row = (
            db_session.query(models.PartnerApplication)
            .filter(models.PartnerApplication.id == uuid.UUID(app_id))
            .first()
        )
        assert row.year_established is None
    finally:
        clear_overrides()


def test_patch_with_invalid_draft_token_returns_403(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "invalidtoken@acme.test"})
        app_id = r.json()["id"]

        r2 = client.patch(
            f"/applications/{app_id}?draft_token=not-the-token",
            json={"legal_name": "Bad Co"},
        )
    finally:
        clear_overrides()
    assert r2.status_code == 403


def test_patch_unknown_application_returns_404(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/applications/{uuid.uuid4()}?draft_token=anything",
            json={"legal_name": "X"},
        )
    finally:
        clear_overrides()
    assert r.status_code == 404


# ---------------- POST /applications/{id}/submit ----------------

def _populate_required(client, app_id, token, **extra):
    payload = {
        "applicant_name": "Founder Name",
        "legal_name": "Submit Co",
        "terms_accepted": True,
    }
    payload.update(extra)
    r = client.patch(f"/applications/{app_id}?draft_token={token}", json=payload)
    assert r.status_code == 200, r.text


def test_submit_succeeds_with_all_required_fields(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "ok@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        _populate_required(client, app_id, token)

        r2 = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["status"] == "submitted"
    assert data["submitted_at"]


def test_submit_fails_when_legal_name_missing(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "missing-legal@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"applicant_name": "Person", "terms_accepted": True},
        )
        r2 = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 422
    body = r2.json()
    assert "legal_name is required" in body["detail"]["errors"]


def test_submit_fails_when_terms_not_accepted(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "no-terms@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={
                "applicant_name": "Person",
                "legal_name": "Acme",
                "terms_accepted": False,
            },
        )
        r2 = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 422
    assert "terms must be accepted" in r2.json()["detail"]["errors"]


def test_submit_twice_rejected(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "twice@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        _populate_required(client, app_id, token)
        client.post(f"/applications/{app_id}/submit?draft_token={token}")

        r2 = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 400


# ---------------- POST /applications/{id}/documents ----------------

def test_upload_document_metadata(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "docs@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]

        r2 = client.post(
            f"/applications/{app_id}/documents?draft_token={token}",
            json={
                "document_type": "fiscal_id",
                "document_name": "fiscal.pdf",
                "file_path": "uploads/x/fiscal.pdf",
                "file_size_bytes": 1234,
                "mime_type": "application/pdf",
            },
        )
    finally:
        clear_overrides()
    assert r2.status_code == 201, r2.text
    doc = r2.json()
    assert doc["document_name"] == "fiscal.pdf"
    assert doc["application_id"] == app_id


def test_upload_document_requires_name_and_path(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "docfail@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        r2 = client.post(
            f"/applications/{app_id}/documents?draft_token={token}",
            json={"document_type": "fiscal_id"},
        )
    finally:
        clear_overrides()
    assert r2.status_code == 422


# ---------------- GET /applications (internal) ----------------

def test_internal_list_as_channel_manager(db_session):
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override_internal_user(db_session, user)
    try:
        client = TestClient(app)
        client.post("/applications", json={"applicant_email": "list1@acme.test"})
        client.post("/applications", json={"applicant_email": "list2@acme.test"})

        r = client.get("/applications")
    finally:
        clear_overrides()
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert data["total"] >= 2


def test_internal_list_denied_for_partner_user(db_session):
    user = make_user(UserRole.partner_user)
    db_session.add(user)
    db_session.commit()
    override_internal_user(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/applications")
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_internal_list_status_filter(db_session):
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override_internal_user(db_session, user)
    try:
        client = TestClient(app)
        # Create + submit one
        r = client.post("/applications", json={"applicant_email": "submitted@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        _populate_required(client, app_id, token)
        client.post(f"/applications/{app_id}/submit?draft_token={token}")
        # Plus a draft
        client.post("/applications", json={"applicant_email": "draft@acme.test"})

        r_sub = client.get("/applications?status=submitted")
        r_draft = client.get("/applications?status=draft")
    finally:
        clear_overrides()
    assert r_sub.status_code == 200
    assert r_draft.status_code == 200
    sub_items = r_sub.json()["items"]
    assert all(i["status"] == "submitted" for i in sub_items)
    draft_items = r_draft.json()["items"]
    assert all(i["status"] == "draft" for i in draft_items)


def test_internal_list_status_under_review_returns_200(db_session):
    """FPRM-191: ?status=under_review previously 500 because the enum
    used 'in_review'. After the rename it's a valid value."""
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override_internal_user(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/applications?status=under_review")
    finally:
        clear_overrides()
    assert r.status_code == 200
    assert "items" in r.json()


def test_internal_list_invalid_status_returns_422(db_session):
    """FPRM-191: unknown status values return 422, not 500."""
    user = make_user(UserRole.channel_manager)
    db_session.add(user)
    db_session.commit()
    override_internal_user(db_session, user)
    try:
        client = TestClient(app)
        r = client.get("/applications?status=garbage")
    finally:
        clear_overrides()
    assert r.status_code == 422
    assert "garbage" in r.json()["detail"]


# ---------------- GET /applications/{id} ----------------

def test_get_application_with_draft_token(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "get@acme.test"})
        app_id, token = r.json()["id"], r.json()["draft_token"]
        r2 = client.get(f"/applications/{app_id}?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 200
    assert r2.json()["applicant_email"] == "get@acme.test"


def test_get_application_no_auth_no_token_returns_401(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "noauth@acme.test"})
        app_id = r.json()["id"]
        r2 = client.get(f"/applications/{app_id}")
    finally:
        clear_overrides()
    assert r2.status_code == 401
