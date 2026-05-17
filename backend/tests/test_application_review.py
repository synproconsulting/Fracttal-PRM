"""Tests for the Sprint 6 application review action endpoints (FPRM-90)."""
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
from models import ApplicationStatus, PartnerApplication, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_application_review.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_application_review.db"):
        try:
            os.remove("./test_application_review.db")
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


def override_db_only(db_session):
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


def _create_and_submit(client, db_session):
    """Create + populate + submit one application; return (id, draft_token).

    Caller must already have at least the get_db override active (public path).
    """
    r = client.post("/applications", json={"applicant_email": f"sub-{uuid.uuid4().hex[:6]}@acme.test"})
    body = r.json()
    app_id, token = body["id"], body["draft_token"]
    client.patch(
        f"/applications/{app_id}?draft_token={token}",
        json={"applicant_name": "Founder", "legal_name": "Acme Inc", "terms_accepted": True},
    )
    sub = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    assert sub.status_code == 200, sub.text
    return app_id, token


# ---------------- approve ----------------


def test_approve_sets_status_approved(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    # Public create+submit
    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    # Reviewer approves
    override_internal_user(db_session, reviewer)
    try:
        r = client.post(f"/applications/{app_id}/approve")
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == app_id
    assert body["status"] == "approved"


def test_approve_rejects_partner_user(db_session):
    user = make_user(UserRole.partner_user)
    db_session.add(user)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, user)
    try:
        r = client.post(f"/applications/{app_id}/approve")
    finally:
        clear_overrides()
    assert r.status_code == 403


def test_approve_from_draft_status_rejected(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()
    override_internal_user(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post("/applications", json={"applicant_email": "draft-only@acme.test"})
        app_id = r.json()["id"]
        r2 = client.post(f"/applications/{app_id}/approve")
    finally:
        clear_overrides()
    assert r2.status_code == 400


# ---------------- reject ----------------


def test_reject_requires_reason(db_session):
    reviewer = make_user(UserRole.channel_ops_admin)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        r = client.post(f"/applications/{app_id}/reject", json={})
    finally:
        clear_overrides()
    assert r.status_code == 422


def test_reject_stores_reason_and_sets_status(db_session):
    reviewer = make_user(UserRole.channel_ops_admin)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        r = client.post(
            f"/applications/{app_id}/reject",
            json={"rejection_reason": "Not enough CMMS experience"},
        )
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Not enough CMMS experience"


# ---------------- request-info ----------------


def test_request_info_sets_status_info_required(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        r = client.post(
            f"/applications/{app_id}/request-info",
            json={"message": "Please attach your tax certificate."},
        )
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "info_required"
    assert "tax certificate" in body["info_request_message"]


def test_request_info_requires_message(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, _token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        r = client.post(f"/applications/{app_id}/request-info", json={})
    finally:
        clear_overrides()
    assert r.status_code == 422


# ---------------- timeline ----------------


def test_timeline_returns_audit_entries_after_review(db_session):
    """Submit publicly, reviewer requests-info, then read timeline via draft_token.

    The internal `GET /applications/{id}/timeline` path validates the Bearer header
    directly (no dependency injection), so test coverage of the internal-JWT path
    needs a real JWT; the public draft_token path is the simpler smoke test.
    """
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, token = _create_and_submit(client, db_session)
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        r_info = client.post(
            f"/applications/{app_id}/request-info",
            json={"message": "Need more info"},
        )
        assert r_info.status_code == 200, r_info.text
    finally:
        clear_overrides()

    override_db_only(db_session)
    try:
        r = client.get(f"/applications/{app_id}/timeline?draft_token={token}")
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    actions = [e["action"] for e in r.json()]
    assert "partner_application.submitted" in actions
    assert "partner_application.info_requested" in actions


def test_timeline_public_with_draft_token(db_session):
    override_db_only(db_session)
    try:
        client = TestClient(app)
        app_id, token = _create_and_submit(client, db_session)
        r2 = client.get(f"/applications/{app_id}/timeline?draft_token={token}")
    finally:
        clear_overrides()
    assert r2.status_code == 200
    actions = [e["action"] for e in r2.json()]
    assert "partner_application.submitted" in actions
