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
from rate_limiter import limiter, get_client_ip


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Minimal stand-in for a Starlette Request for unit-testing get_client_ip."""
    def __init__(self, headers, peer="9.9.9.9"):
        self.headers = headers
        self.client = _FakeClient(peer)


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


# --- FPRM-460 regression: the limiter must engage behind a proxy ----------------

def test_get_client_ip_resolution():
    """Unit-test the proxy-aware key func directly.

    Old behaviour keyed on the TCP peer only (get_remote_address); behind
    Railway's edge proxy that peer is the proxy (and rotates per request), so the
    per-IP bucket never accumulated. The new key func must prefer the proxy's
    real-client header.
    """
    # Envoy edge header wins over X-Forwarded-For.
    assert get_client_ip(_FakeRequest({
        "X-Envoy-External-Address": "3.3.3.3",
        "X-Forwarded-For": "4.4.4.4",
    })) == "3.3.3.3"
    # Left-most X-Forwarded-For hop = original client when no Envoy header.
    assert get_client_ip(_FakeRequest({"X-Forwarded-For": "5.5.5.5, 6.6.6.6"})) == "5.5.5.5"
    # Garbage / forged non-IP header falls back to the TCP peer (no weird keys).
    assert get_client_ip(_FakeRequest({"X-Forwarded-For": "not-an-ip"})) == "9.9.9.9"
    # No proxy headers (direct hit) -> TCP peer.
    assert get_client_ip(_FakeRequest({})) == "9.9.9.9"


def test_limiter_keys_on_forwarded_client_ip(rate_limited):
    """End-to-end: the limit accumulates per real client IP from the forwarded
    header, distinct clients get independent buckets, and the 429 carries
    rate-limit + Retry-After headers.

    This would have caught the inert-in-prod bug: under the old get_remote_address
    keying every X-Forwarded-For value collapsed to the shared ``testclient`` peer,
    so client B below would wrongly inherit client A's count (no independent
    bucket) and the proxy-keyed accumulation could not be observed at all.
    """
    client = TestClient(app)

    # Client A (forwarded 1.1.1.1), login limit 3/minute -> 4th request blocked.
    a = [client.post("/auth/login",
                     json={"email": "a@test.com", "password": "x"},
                     headers={"X-Forwarded-For": "1.1.1.1"}).status_code
         for _ in range(4)]
    assert a == [401, 401, 401, 429], a

    # Client B is a *different* forwarded IP -> independent bucket, still allowed.
    b = client.post("/auth/login",
                    json={"email": "b@test.com", "password": "x"},
                    headers={"X-Forwarded-For": "2.2.2.2"})
    assert b.status_code == 401, b.status_code

    # The 429 surfaces the rate-limit headers so engagement is observable in prod.
    blocked = client.post("/auth/login",
                          json={"email": "a@test.com", "password": "x"},
                          headers={"X-Forwarded-For": "1.1.1.1"})
    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers.keys()}
    assert any(k.lower().startswith("x-ratelimit") for k in blocked.headers.keys()), \
        dict(blocked.headers)
