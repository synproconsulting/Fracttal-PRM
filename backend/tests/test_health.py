import os
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import get_db

client = TestClient(app)


def _db_connected():
    db = MagicMock()
    yield db


def _db_unreachable():
    db = MagicMock()
    db.execute.side_effect = Exception("DB down")
    yield db


def test_health_returns_200():
    app.dependency_overrides[get_db] = _db_connected
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


def test_health_response_shape():
    app.dependency_overrides[get_db] = _db_connected
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "database" in data


def test_health_service_name():
    app.dependency_overrides[get_db] = _db_connected
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.json()["service"] == "fracttal-prm-backend"


def test_health_db_unreachable_still_returns_200():
    app.dependency_overrides[get_db] = _db_unreachable
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["database"] == "unreachable"
