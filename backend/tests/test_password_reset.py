import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import get_db
from models import PasswordResetToken

client = TestClient(app)


def _make_override(first_return):
    def _override():
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = first_return
        yield db
    return _override


def test_password_reset_request_returns_200_even_for_unknown_email():
    app.dependency_overrides[get_db] = _make_override(None)
    try:
        response = client.post(
            "/auth/password-reset/request",
            json={"email": "unknown@example.com"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


def test_password_reset_request_sends_email_for_known_user():
    """FPRM-462 — a known email triggers send_email with the reset link, and the
    token is never returned in the response."""
    user = MagicMock()
    user.email = "known@example.com"
    user.id = "00000000-0000-0000-0000-000000000001"
    app.dependency_overrides[get_db] = _make_override(user)
    try:
        with patch("routers.auth_router.send_email") as mock_send:
            response = client.post(
                "/auth/password-reset/request",
                json={"email": "known@example.com"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "token" not in response.json()
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "known@example.com"
    assert "/reset-password?token=" in kwargs["body_html"]


def test_password_reset_confirm_invalid_token():
    app.dependency_overrides[get_db] = _make_override(None)
    try:
        response = client.post(
            "/auth/password-reset/confirm",
            json={"token": "bad-token", "new_password": "newpass123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


def test_password_reset_confirm_used_token():
    mock_token = MagicMock(spec=PasswordResetToken)
    mock_token.used = True
    mock_token.expires_at = datetime.utcnow() + timedelta(hours=1)
    app.dependency_overrides[get_db] = _make_override(mock_token)
    try:
        response = client.post(
            "/auth/password-reset/confirm",
            json={"token": "used-token", "new_password": "newpass123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


def test_password_reset_confirm_expired_token():
    mock_token = MagicMock(spec=PasswordResetToken)
    mock_token.used = False
    mock_token.expires_at = datetime.utcnow() - timedelta(hours=2)
    app.dependency_overrides[get_db] = _make_override(mock_token)
    try:
        response = client.post(
            "/auth/password-reset/confirm",
            json={"token": "expired-token", "new_password": "newpass123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
