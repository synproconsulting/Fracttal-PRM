"""Tests for backend/notifications.py and notification wiring (FPRM-93)."""
import os
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import User
from roles import UserRole
import notifications


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_notifications.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_notifications.db"):
        try:
            os.remove("./test_notifications.db")
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


# ---------------- send_email dev mode ----------------


def test_send_email_dev_mode_does_not_call_smtp(monkeypatch, capsys):
    """When SMTP_HOST is unset, send_email prints to stdout and never calls smtplib."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    with patch("smtplib.SMTP") as smtp_mock:
        notifications.send_email("a@b.com", "Hi", "<p>Body</p>")
    smtp_mock.assert_not_called()
    out = capsys.readouterr().out
    assert "[DEV MODE EMAIL]" in out
    assert "Hi" in out


def test_send_email_uses_smtp_when_configured(monkeypatch):
    """When SMTP env vars are present, send_email calls smtplib."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_FROM", "noreply@fracttal.com")
    with patch("smtplib.SMTP") as smtp_mock:
        instance = smtp_mock.return_value.__enter__.return_value
        notifications.send_email("a@b.com", "Hi", "<p>x</p>")
    smtp_mock.assert_called_once()
    instance.starttls.assert_called_once()
    instance.login.assert_called_once_with("user", "pw")
    instance.sendmail.assert_called_once()


def test_send_email_swallows_smtp_errors(monkeypatch):
    """SMTP failure must not raise — endpoints depend on this."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("boom")):
        # Must not raise
        notifications.send_email("a@b.com", "Hi", "<p>x</p>")


# ---------------- lifecycle wiring ----------------


def _create_and_submit_application(client, db_session):
    r = client.post(
        "/applications",
        json={"applicant_email": f"notify-{uuid.uuid4().hex[:6]}@acme.test"},
    )
    body = r.json()
    app_id, token = body["id"], body["draft_token"]
    client.patch(
        f"/applications/{app_id}?draft_token={token}",
        json={"applicant_name": "Founder", "legal_name": "Acme Inc", "terms_accepted": True},
    )
    return app_id, token


def test_submit_calls_notify_application_submitted(db_session):
    override_db_only(db_session)
    try:
        client = TestClient(app)
        app_id, token = _create_and_submit_application(client, db_session)
        with patch("routers.applications_router.notify_application_submitted") as mock_notify:
            r = client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    mock_notify.assert_called_once()


def test_approve_calls_notify_application_approved(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, token = _create_and_submit_application(client, db_session)
        client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        with patch("routers.applications_router.notify_application_approved") as mock_notify:
            r = client.post(f"/applications/{app_id}/approve")
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    mock_notify.assert_called_once()


def test_reject_calls_notify_application_rejected(db_session):
    reviewer = make_user(UserRole.channel_ops_admin)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, token = _create_and_submit_application(client, db_session)
        client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        with patch("routers.applications_router.notify_application_rejected") as mock_notify:
            r = client.post(
                f"/applications/{app_id}/reject",
                json={"rejection_reason": "Insufficient experience"},
            )
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    # signature: (application, rejection_reason)
    assert args[1] == "Insufficient experience"


def test_request_info_calls_notify_info_required(db_session):
    reviewer = make_user(UserRole.channel_manager)
    db_session.add(reviewer)
    db_session.commit()

    override_db_only(db_session)
    client = TestClient(app)
    try:
        app_id, token = _create_and_submit_application(client, db_session)
        client.post(f"/applications/{app_id}/submit?draft_token={token}")
    finally:
        clear_overrides()

    override_internal_user(db_session, reviewer)
    try:
        with patch("routers.applications_router.notify_info_required") as mock_notify:
            r = client.post(
                f"/applications/{app_id}/request-info",
                json={"message": "Please attach tax cert"},
            )
    finally:
        clear_overrides()
    assert r.status_code == 200, r.text
    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    assert args[1] == "Please attach tax cert"
