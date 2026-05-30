"""Sprint 24 / FPRM-418 / AD-40 -- one shared document-type vocabulary.

Every upload surface (Documents page, quote-attach, Document Rules) sources its
dropdown from the single GET /config/document-types list via the shared
DocumentTypeSelect component. These tests pin the API-level guarantee that
underpins that: the endpoint is the single source, includes the seeded KYC
types (incl. ``nda``), and a type added through the vocabulary admin POST
immediately appears in that same list -- so it appears on all surfaces.

This file intentionally does NOT modify test_document_types_config.py (its
contract is unchanged); it adds the explicit unification assertions.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import DocumentTypeConfig, User
from roles import UserRole


@pytest.fixture()
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=eng)
        eng.dispose()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed(db, *codes):
    for c in codes:
        db.add(DocumentTypeConfig(id=uuid.uuid4(), code=c, label=c.replace("_", " ").title(), is_active=True))
    db.commit()


def _admin(db):
    u = User(id=uuid.uuid4(), email=f"a-{uuid.uuid4().hex[:6]}@t", hashed_password="x",
             role=UserRole.system_admin.value, is_active=True)
    db.add(u); db.commit()
    app.dependency_overrides[get_current_user] = lambda: u
    return u


def test_vocabulary_is_single_source_with_seeded_kyc_types(client, db):
    _seed(db, "fiscal_id", "nda", "contract", "quote_acceptance")
    codes = [t["code"] for t in client.get("/config/document-types").json()["items"]]
    # The same list every surface fetches -- nda must be present (the divergence bug).
    assert "nda" in codes
    assert {"fiscal_id", "contract", "quote_acceptance"} <= set(codes)


def test_added_type_appears_in_the_shared_list(client, db):
    _seed(db, "nda")
    _admin(db)
    new_code = f"tax_clearance_{uuid.uuid4().hex[:6]}"
    r = client.post("/config/document-types",
                    json={"code": new_code, "label": "Tax Clearance"},
                    headers={"Authorization": "Bearer fake"})
    assert r.status_code == 201, r.text
    # A type added via the vocabulary admin is immediately in the single list
    # that every surface reads -> it appears everywhere.
    codes = [t["code"] for t in client.get("/config/document-types").json()["items"]]
    assert new_code in codes
