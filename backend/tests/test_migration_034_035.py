"""Sprint 21 / AD-33 schema migrations 034 + 035 -- model-level guarantees.

These tests exercise the schema *as the models declare it*, which is what
Base.metadata.create_all builds for the test database. The Alembic
migration files themselves are validated separately by being importable
(see ``test_migration_modules_importable`` below) so a syntax error fails
CI even though the actual upgrade()/downgrade() steps can't run against
sqlite (they use postgres-specific casts and gen_random_uuid()).
"""
import importlib
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
import models  # noqa: F401
from models import DocumentReference, PartnerDocument, PartnerOrganization, User


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# ----------------------------------------------------------------------------
# Migration 034 -- extend partner_documents
# ----------------------------------------------------------------------------


def test_partner_documents_has_file_data_column():
    """Migration 034 added file_data Text nullable."""
    cols = {c.name: c for c in PartnerDocument.__table__.columns}
    assert "file_data" in cols
    assert cols["file_data"].nullable is True


def test_partner_documents_file_path_is_nullable():
    """Migration 034 relaxed file_path to nullable."""
    cols = {c.name: c for c in PartnerDocument.__table__.columns}
    assert cols["file_path"].nullable is True


def test_partner_document_with_file_data_only_persists(db):
    """Sprint 21 upload path: file_data filled, file_path null."""
    org = PartnerOrganization(
        id=uuid.uuid4(), legal_name="Org",
        program_type="distributor", partner_category="reseller", status="active",
    )
    user = User(
        id=uuid.uuid4(), email=f"u-{uuid.uuid4().hex[:6]}@t",
        hashed_password="x", role="system_admin", is_active=True,
    )
    db.add_all([org, user])
    db.commit()

    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=org.id,
        document_type="nda",
        document_name="centralised.pdf",
        file_path=None,
        file_data="aGVsbG8=",
        uploaded_by_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    assert doc.file_data == "aGVsbG8="
    assert doc.file_path is None


# ----------------------------------------------------------------------------
# Migration 035 -- create document_references
# ----------------------------------------------------------------------------


def test_document_references_table_exists(engine):
    """Migration 035 created the join table."""
    insp = inspect(engine)
    assert "document_references" in set(insp.get_table_names())


def test_document_references_has_expected_columns():
    cols = {c.name for c in DocumentReference.__table__.columns}
    assert {"id", "document_id", "entity_type", "entity_id", "label", "created_at"}.issubset(cols)


def test_document_references_indexes_declared():
    indexes = {idx.name for idx in DocumentReference.__table__.indexes}
    assert "ix_doc_refs_entity" in indexes
    assert "ix_doc_refs_document" in indexes


# ----------------------------------------------------------------------------
# Migration files themselves -- importable (catch syntax errors in CI)
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("mod_name", [
    "alembic.versions.034_extend_partner_documents",
    "alembic.versions.035_create_document_references",
    "alembic.versions.036_backfill_drop_quote_documents",
])
def test_migration_modules_importable(mod_name):
    # Alembic migration files use leading-digit module names which Python
    # doesn't accept as identifiers; import via importlib.machinery so the
    # file is exec'd and any syntax errors raise here.
    import importlib.util
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = mod_name.replace(".", "/") + ".py"
    full = os.path.join(here, rel)
    assert os.path.exists(full), f"missing migration file: {full}"
    spec = importlib.util.spec_from_file_location(mod_name, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert hasattr(mod, "revision")
