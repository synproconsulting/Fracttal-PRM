import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import models  # noqa: F401  ensures all models register with Base.metadata
from database import engine
from models import Base


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
