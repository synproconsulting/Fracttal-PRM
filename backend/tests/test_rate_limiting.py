"""Sprint 25 PR B / FPRM-455 / AD-44 — auth + public-endpoint rate limiting.

The limiter is disabled suite-wide (conftest) so the new per-IP limits do not
trip the rest of the suite. This module re-enables it locally with low test-time
limits and asserts that login, password-reset, and the public application
endpoint return 429 once their limit is exceeded — while under-limit requests are
processed normally (401 / 200 / 201).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app
from rate_limiter import limiter


@pytest.fixture
def rate_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "3/minute")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET", "2/minute")
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_APP", "2/minute")
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_rate_limits_enforced(rate_limited):
    client = TestClient(app)

    # login — 3/minute: three processed (401 bad creds), fourth blocked (429).
    login = [client.post("/auth/login", json={"email": "nobody@test.com",
             "password": "wrong"}).status_code for _ in range(4)]
    assert login == [401, 401, 401, 429], login

    # password-reset request — 2/minute: two processed (always 200), third 429.
    pr = [client.post("/auth/password-reset/request",
          json={"email": "nobody@test.com"}).status_code for _ in range(3)]
    assert pr == [200, 200, 429], pr

    # public application create — 2/minute: two created (201), third 429.
    apps = [client.post("/applications",
            json={"applicant_email": "x@test.com"}).status_code for _ in range(3)]
    assert apps == [201, 201, 429], apps


def test_limiter_disabled_does_not_block(rate_limited):
    # With the limiter disabled (default suite state), many calls all succeed.
    limiter.enabled = False
    client = TestClient(app)
    codes = [client.post("/auth/login", json={"email": "nobody@test.com",
             "password": "wrong"}).status_code for _ in range(8)]
    assert all(c == 401 for c in codes), codes
