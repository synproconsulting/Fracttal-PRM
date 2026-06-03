import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import models  # noqa: F401  ensures all models register with Base.metadata
from database import engine
from models import Base
from rate_limiter import limiter


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiter():
    """Sprint 25 PR B / FPRM-455 — disable slowapi globally for the suite so the
    new per-IP limits on login / password-reset / public-application endpoints do
    not trip across the many tests that share the ``testclient`` source IP. The
    dedicated rate-limit test (test_rate_limiting.py) re-enables it locally."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables before the test session, drop them after.

    Pytest runs against the engine bound to DATABASE_URL (sqlite default in CI).
    Alembic migrations run in production against PostgreSQL; here we use
    Base.metadata.create_all so unit tests can inspect table structure without
    needing a separate migration step.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
