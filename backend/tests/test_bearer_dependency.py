"""FPRM-104: confirm dependency_overrides[get_optional_bearer_user] is honoured
by the timeline and messages endpoints (and the existing get_application path).

Pre-FPRM-104, these endpoints called a private ``_user_from_bearer`` helper
directly, so test fixtures could not inject a fake authenticated user via
FastAPI's ``dependency_overrides`` — a real JWT had to be minted. After
FPRM-104, ``get_optional_bearer_user`` is a FastAPI dependency and overrides
work.
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
from auth import get_optional_bearer_user
from database import Base, get_db
import models  # noqa: F401
from models import ApplicationStatus, PartnerApplication, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_bearer_dependency.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_bearer_dependency.db"):
        try:
            os.remove("./test_bearer_dependency.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_optional_bearer_user, None)


def _make_admin(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name="Admin Tester",
        role=UserRole.system_admin.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_application(db_session) -> PartnerApplication:
    app_record = PartnerApplication(
        id=uuid.uuid4(),
        applicant_email="x@example.com",
        applicant_name="X",
        legal_name="X Co",
        status=ApplicationStatus.submitted,
        draft_token="t-" + uuid.uuid4().hex,
        terms_accepted=True,
    )
    db_session.add(app_record)
    db_session.commit()
    return app_record


def test_get_application_honours_dependency_override(client, db_session):
    admin = _make_admin(db_session)
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: admin

    response = client.get(f"/applications/{app_record.id}")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(app_record.id)


def test_get_application_overridden_to_none_returns_401(client, db_session):
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: None

    response = client.get(f"/applications/{app_record.id}")
    assert response.status_code == 401
    assert "draft_token" in response.json()["detail"]


def test_timeline_honours_dependency_override(client, db_session):
    admin = _make_admin(db_session)
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: admin

    response = client.get(f"/applications/{app_record.id}/timeline")
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_timeline_overridden_to_none_returns_401(client, db_session):
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: None

    response = client.get(f"/applications/{app_record.id}/timeline")
    assert response.status_code == 401


def test_list_messages_honours_dependency_override(client, db_session):
    admin = _make_admin(db_session)
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: admin

    response = client.get(f"/applications/{app_record.id}/messages")
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_post_message_honours_dependency_override(client, db_session):
    admin = _make_admin(db_session)
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: admin

    response = client.post(
        f"/applications/{app_record.id}/messages",
        json={"message": "hello from admin"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["message"] == "hello from admin"
    assert body["sender_type"] == "internal"
    assert body["sender_email"] == admin.email


def test_post_message_overridden_to_none_returns_401(client, db_session):
    app_record = _make_application(db_session)
    app.dependency_overrides[get_optional_bearer_user] = lambda: None

    response = client.post(
        f"/applications/{app_record.id}/messages",
        json={"message": "anon"},
    )
    assert response.status_code == 401


def test_draft_token_path_still_works_without_bearer_override(client, db_session):
    """draft_token query param should still authorise public access, even when
    get_optional_bearer_user is not overridden (returns None by default)."""
    app_record = _make_application(db_session)

    response = client.get(
        f"/applications/{app_record.id}/timeline",
        params={"draft_token": app_record.draft_token},
    )
    assert response.status_code == 200
