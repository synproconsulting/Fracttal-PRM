"""Sprint 25 PR A / FPRM-451 / AD-43 — security response-headers middleware.

Every response (public + authenticated) must carry the baseline security headers
set centrally in main.py. CORS behaviour is intentionally not asserted here (out
of scope this sprint).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from main import app
from auth import get_current_user
from models import User

EXPECTED_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}


def test_security_headers_on_public_response():
    client = TestClient(app)
    r = client.get("/")  # public root, no auth, no DB dependency
    assert r.status_code == 200
    for header, value in EXPECTED_HEADERS.items():
        assert r.headers.get(header) == value, f"{header} missing/wrong: {r.headers.get(header)}"


def test_security_headers_on_authenticated_response():
    user = User(id=uuid.uuid4(), email="hdr@test.com", hashed_password="x",
                role="system_admin", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        r = client.get("/auth/me")
        assert r.status_code == 200
        for header, value in EXPECTED_HEADERS.items():
            assert r.headers.get(header) == value, header
    finally:
        app.dependency_overrides.clear()
