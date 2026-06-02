"""Sprint 25 PR A / FPRM-453 — generic 500 handler (no internal-detail leakage).

Unhandled exceptions return a generic {"detail": "Internal server error"} 500
with no traceback in the body; intended HTTPException 4xx detail strings are
preserved unchanged.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app


# Throwaway routes registered on the app for this test only.
@app.get("/__test_boom_unexpected__")
def _boom_unexpected():
    raise RuntimeError("kaboom-secret-internal-detail")


@app.get("/__test_teapot__")
def _teapot():
    raise HTTPException(status_code=404, detail="Not found")


def test_unhandled_exception_returns_generic_500():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/__test_boom_unexpected__")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}
    # No internal detail or traceback leaks into the body.
    assert "kaboom" not in r.text
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text


def test_httpexception_detail_preserved():
    client = TestClient(app)
    r = client.get("/__test_teapot__")
    assert r.status_code == 404
    assert r.json()["detail"] == "Not found"
