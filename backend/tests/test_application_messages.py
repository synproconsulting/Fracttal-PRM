"""Tests for the Sprint 6 application messages and resubmit flow (FPRM-91)."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user, create_access_token
from database import Base, get_db
import models  # noqa: F401
from models import PartnerApplication, ApplicationStatus, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_application_messages.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_application_messages.db"):
        try:
            os.remove("./test_application_messages.db")
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


def _make_submitted(client, db_session):
    r = client.post("/applications", json={"applicant_email": f"msg-{uuid.uuid4().hex[:6]}@acme.test"})
    body = r.json()
    app_id, token = body["id"], body["draft_token"]
    client.patch(
        f"/applications/{app_id}?draft_token={token}",
        json={"applicant_name": "P", "legal_name": "Acme", "terms_accepted": True},
    )
    client.post(f"/applications/{app_id}/submit?draft_token={token}")
    return app_id, token


# ------------- messages: applicant posts via draft_token -------------


def test_post_message_as_applicant(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        app_id, token = _make_submitted(client, db_session)
        r = client.post(
            f"/applications/{app_id}/messages?draft_token={token}",
            json={"message": "Hi reviewer", "sender_email": "applicant@acme.test"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["sender_type"] == "applicant"
        assert body["message"] == "Hi reviewer"

        r2 = client.get(f"/applications/{app_id}/messages?draft_token={token}")
        assert r2.status_code == 200
        items = r2.json()
        assert len(items) == 1
        assert items[0]["message"] == "Hi reviewer"
    finally:
        clear_overrides()


def test_post_message_requires_text(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        app_id, token = _make_submitted(client, db_session)
        r = client.post(
            f"/applications/{app_id}/messages?draft_token={token}",
            json={"sender_email": "applicant@acme.test"},
        )
        assert r.status_code == 422
    finally:
        clear_overrides()


def test_message_bad_token_403(db_session):
    override_db(db_session)
    try:
        client = TestClient(app)
        app_id, _ = _make_submitted(client, db_session)
        r = client.get(f"/applications/{app_id}/messages?draft_token=wrong")
        assert r.status_code == 403
    finally:
        clear_overrides()


# ------------- messages: internal posts via JWT -------------


def test_post_message_as_internal(db_session):
    """The message endpoint reads the Authorization header directly (not via
    Depends(get_current_user)), so the dependency override is not enough — we
    must mint a real JWT for the reviewer."""
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db(db_session)
    client = TestClient(app)
    try:
        app_id, _ = _make_submitted(client, db_session)

        token = create_access_token(
            {"sub": str(reviewer.id), "email": reviewer.email, "role": reviewer.role}
        )
        r = client.post(
            f"/applications/{app_id}/messages",
            json={"message": "Need tax cert please"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["sender_type"] == "internal"
        assert body["sender_email"] == reviewer.email
    finally:
        clear_overrides()


# ------------- resubmit from info_required -------------


def test_resubmit_from_info_required_resets_status(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db(db_session)
    client = TestClient(app)
    try:
        app_id, token = _make_submitted(client, db_session)
    finally:
        clear_overrides()

    # Reviewer requests info
    override_internal_user(db_session, reviewer)
    try:
        client.post(
            f"/applications/{app_id}/request-info",
            json={"message": "Please add more detail"},
        )
    finally:
        clear_overrides()

    # Applicant edits + resubmits via draft_token
    override_db(db_session)
    try:
        r = client.patch(
            f"/applications/{app_id}?draft_token={token}",
            json={"additional_info": "Here is more detail"},
        )
        assert r.status_code == 200
        r2 = client.post(f"/applications/{app_id}/submit?draft_token={token}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "submitted"
    finally:
        clear_overrides()
