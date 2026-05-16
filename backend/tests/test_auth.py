import os
import sys
from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import get_db
from auth import hash_password, JWT_SECRET, JWT_ALGORITHM
from models import User

client = TestClient(app)


def _make_override(first_return):
    def _override():
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = first_return
        yield db
    return _override


def test_register_success():
    app.dependency_overrides[get_db] = _make_override(None)
    try:
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "secret123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert "id" in response.json()


def test_register_duplicate_email():
    existing = MagicMock(spec=User)
    app.dependency_overrides[get_db] = _make_override(existing)
    try:
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "secret123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409


def test_login_success():
    mock_user = MagicMock(spec=User)
    mock_user.hashed_password = hash_password("secret123")
    mock_user.is_active = True
    mock_user.id = "test-uuid"
    mock_user.email = "test@example.com"
    mock_user.role = "partner_user"

    app.dependency_overrides[get_db] = _make_override(mock_user)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "secret123"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    mock_user = MagicMock(spec=User)
    mock_user.hashed_password = hash_password("correct_password")
    mock_user.is_active = True

    app.dependency_overrides[get_db] = _make_override(mock_user)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong_password"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_login_no_such_user():
    app.dependency_overrides[get_db] = _make_override(None)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_protected_route_without_token():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_health_still_public():
    response = client.get("/health")
    assert response.status_code == 200


def test_public_routes_no_auth_required():
    assert client.get("/health").status_code == 200
    r = client.post("/auth/login", json={})
    assert r.status_code != 401


def test_private_route_requires_auth():
    response = client.get("/auth/me")
    assert response.status_code == 401


def _register_login_override():
    """Override get_db so register sees no existing user, and login sees the user we just created."""
    state = {"user": None}

    def _override():
        db = MagicMock()

        def _add(obj):
            if isinstance(obj, User):
                # SQLAlchemy column defaults only fire on INSERT, so simulate them here
                # so the subsequent login() request passes the is_active guard.
                obj.is_active = True
                state["user"] = obj

        db.query.return_value.filter.return_value.first.side_effect = lambda: state["user"]
        db.add.side_effect = _add
        db.refresh.return_value = None
        db.commit.return_value = None
        yield db

    return _override


def test_register_with_role_persists_role_in_jwt():
    """FPRM-73: POST /auth/register must honor the submitted role; login JWT must reflect it."""
    app.dependency_overrides[get_db] = _register_login_override()
    try:
        reg = client.post(
            "/auth/register",
            json={
                "email": "admin@example.com",
                "password": "secret123",
                "role": "system_admin",
            },
        )
        assert reg.status_code == 201, reg.text

        login = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "secret123"},
        )
        assert login.status_code == 200, login.text

        token = login.json()["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["role"] == "system_admin"
        assert payload["email"] == "admin@example.com"
    finally:
        app.dependency_overrides.clear()


def test_register_without_role_defaults_to_partner_user():
    """Regression: omitting role must still default to partner_user."""
    app.dependency_overrides[get_db] = _register_login_override()
    try:
        reg = client.post(
            "/auth/register",
            json={"email": "puser@example.com", "password": "secret123"},
        )
        assert reg.status_code == 201, reg.text

        login = client.post(
            "/auth/login",
            json={"email": "puser@example.com", "password": "secret123"},
        )
        assert login.status_code == 200, login.text
        payload = jwt.decode(
            login.json()["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        assert payload["role"] == "partner_user"
    finally:
        app.dependency_overrides.clear()


def test_register_with_invalid_role_rejected():
    """Pydantic must reject role values outside the UserRole enum."""
    app.dependency_overrides[get_db] = _make_override(None)
    try:
        response = client.post(
            "/auth/register",
            json={
                "email": "bogus@example.com",
                "password": "secret123",
                "role": "godmode",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
