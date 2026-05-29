"""Sprint 23 PR A -- Sprint 22 carry-forward bugs/gaps.

Covers:
  S1 (FPRM-387) migration 039 importability + idempotent seed + reconcile;
               universal gate on the version-upload path.
  S3 (FPRM-389) partner attach proof + mark own-org quote accepted (AD-35).
  S4 (FPRM-390) partner_admin version revert (own org) + audit + uploaded_by_name.
  S5 (FPRM-391) 25 MB size cap replaces the type allowlist (AD-37).
"""
import base64
import importlib.util
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
from models import (
    AuditLog,
    DealRegistration,
    DocumentReference,
    DocumentStatus,
    DocumentTypeConfig,
    DocumentTypeRule,
    DocumentVersion,
    PartnerDocument,
    PartnerOrganization,
    Quote,
    User,
)
from roles import UserRole


_PDF = b"%PDF-1.4\n%%EOF"
_PDF_B64 = base64.b64encode(_PDF).decode()
_PDF_V2 = b"%PDF-1.4\nv2\n%%EOF"
_PDF_V2_B64 = base64.b64encode(_PDF_V2).decode()


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        from sqlalchemy import text
        s.rollback()
        for tbl in (
            "document_versions", "document_references", "partner_documents",
            "document_type_rules", "document_types", "quote_line_items",
            "quote_versions", "quotes", "deal_registrations", "audit_log",
            "users", "partner_organizations",
        ):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _partner(db, name="Org"):
    p = PartnerOrganization(
        id=uuid.uuid4(), legal_name=f"{name} {uuid.uuid4().hex[:4]}",
        program_type="distributor", partner_category="reseller", status="active",
    )
    db.add(p); db.commit()
    return p


def _user(db, role, partner_org_id=None, full_name=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@t",
        hashed_password="x", role=role, is_active=True,
        partner_org_id=partner_org_id, full_name=full_name,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _upload(client, partner_id, document_type="nda", document_name="x.pdf",
            payload_bytes=_PDF, mime_type="application/pdf", size=None):
    return client.post(
        f"/partners/{partner_id}/documents",
        json={
            "document_type": document_type,
            "document_name": document_name,
            "file_data": base64.b64encode(payload_bytes).decode(),
            "file_size_bytes": size if size is not None else len(payload_bytes),
            "mime_type": mime_type,
        },
    )


# ============================================================
# S1 -- migration 039
# ============================================================


def _load_039():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full = os.path.join(here, "alembic", "versions", "039_seed_document_type_rules.py")
    spec = importlib.util.spec_from_file_location("mig039", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_039_importable_and_revision():
    mod = _load_039()
    assert mod.revision == "039"
    assert mod.down_revision == "038"
    assert hasattr(mod, "upgrade") and hasattr(mod, "downgrade")
    # The five KYC rule types are introduced here.
    assert set(mod.SEED_RULES) == {
        "proof_of_fiscal_domicile", "w9", "insurance_certificate",
        "nda", "security_assessment",
    }
    # Vocabulary seed also includes contract + quote_acceptance.
    codes = {c for c, _ in mod.SEED_VOCAB}
    assert {"contract", "quote_acceptance"}.issubset(codes)


def test_migration_039_seed_is_idempotent(engine, db):
    """Running _ensure_rule / _ensure_vocab twice inserts exactly one row."""
    mod = _load_039()
    with engine.begin() as conn:
        idexpr, t, f, now = mod._dialect_bits(conn)
        for _ in range(2):
            mod._ensure_vocab(conn, "w9", "W-9", idexpr, t, now)
            mod._ensure_rule(conn, "w9", idexpr, t, f, now, "KYC")
    assert db.query(DocumentTypeRule).filter_by(document_type="w9").count() == 1
    assert db.query(DocumentTypeConfig).filter_by(code="w9").count() == 1
    rule = db.query(DocumentTypeRule).filter_by(document_type="w9").first()
    assert rule.requires_approval is True
    assert rule.auto_approve is False


def test_migration_039_reconcile_creates_default_rule(engine, db):
    """An in-use document_type with no rule gets a default requires_approval rule."""
    mod = _load_039()
    with engine.begin() as conn:
        idexpr, t, f, now = mod._dialect_bits(conn)
        # Simulate reconcile for an in-use type.
        mod._ensure_vocab(conn, "custom_in_use", "Custom In Use", idexpr, t, now)
        mod._ensure_rule(conn, "custom_in_use", idexpr, t, f, now, "reconciled")
    rule = db.query(DocumentTypeRule).filter_by(document_type="custom_in_use").first()
    assert rule is not None
    assert rule.requires_approval is True and rule.auto_approve is False


# ============================================================
# S1 #7 -- universal gate on the version-upload path
# ============================================================


def test_version_upload_applies_rule_case_insensitively(client, db):
    """A new version of a doc whose type has an auto_approve rule (stored with
    different casing) is set approved -- the version path uses the shared
    case-insensitive lookup (FPRM-386/387)."""
    p = _partner(db)
    _auth(_user(db, UserRole.channel_manager.value))
    db.add(DocumentTypeRule(id=uuid.uuid4(), document_type="REPORT",
                            requires_approval=False, auto_approve=True))
    db.commit()
    up = _upload(client, p.id, document_type="report").json()
    doc_id = up["id"]
    r = client.post(f"/partners/{p.id}/documents/{doc_id}/versions",
                    json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)})
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(PartnerDocument.id == uuid.UUID(doc_id)).first()
    assert doc.status == DocumentStatus.approved


# ============================================================
# S5 -- size cap replaces type allowlist
# ============================================================


def test_upload_arbitrary_type_succeeds(client, db):
    """A non-PDF/non-image type uploads fine -- no server-side type allowlist."""
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = _upload(client, p.id, document_type="nda", document_name="data.zip",
                payload_bytes=b"PK\x03\x04zipcontent", mime_type="application/zip")
    assert r.status_code == 201, r.text
    assert r.json()["mime_type"] == "application/zip"


def test_upload_over_25mb_declared_returns_422(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = _upload(client, p.id, document_type="nda", size=26214401)  # 25MB + 1
    assert r.status_code == 422
    assert "25 MB" in r.json()["detail"]


def test_upload_at_25mb_boundary_succeeds(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    # Declared exactly 25 MB with a tiny real payload -- accepted.
    r = _upload(client, p.id, document_type="nda", size=26214400)
    assert r.status_code == 201, r.text


# ============================================================
# S4 -- partner_admin revert (own org) + audit + uploaded_by_name
# ============================================================


def _two_version_doc(client, db, partner, uploader):
    _auth(uploader)
    up = _upload(client, partner.id, document_type="nda").json()
    doc_id = up["id"]
    client.post(f"/partners/{partner.id}/documents/{doc_id}/versions",
                json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)})
    versions = client.get(f"/partners/{partner.id}/documents/{doc_id}/versions").json()
    return doc_id, versions


def test_partner_admin_reverts_own_org_doc(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    doc_id, versions = _two_version_doc(client, db, p, cm)
    v1 = next(v for v in versions if v["version_number"] == 1)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    _auth(pa)
    r = client.post(f"/partners/{p.id}/documents/{doc_id}/versions/{v1['id']}/revert")
    assert r.status_code == 200, r.text
    assert r.json()["current_version_number"] == 1
    audit = (db.query(AuditLog)
             .filter(AuditLog.action == "document.version_reverted")
             .filter(AuditLog.object_id == uuid.UUID(doc_id)).first())
    assert audit is not None


def test_partner_admin_cannot_revert_other_org(client, db):
    p_a = _partner(db, "A")
    cm = _user(db, UserRole.channel_manager.value)
    doc_id, versions = _two_version_doc(client, db, p_a, cm)
    v1 = next(v for v in versions if v["version_number"] == 1)
    pa_b = _user(db, UserRole.partner_admin.value, partner_org_id=_partner(db, "B").id)
    _auth(pa_b)
    r = client.post(f"/partners/{p_a.id}/documents/{doc_id}/versions/{v1['id']}/revert")
    assert r.status_code in (403, 404)  # tenant guard -- own-org mismatch


def test_partner_user_cannot_revert(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    doc_id, versions = _two_version_doc(client, db, p, cm)
    v1 = next(v for v in versions if v["version_number"] == 1)
    pu = _user(db, UserRole.partner_user.value, partner_org_id=p.id)
    _auth(pu)
    r = client.post(f"/partners/{p.id}/documents/{doc_id}/versions/{v1['id']}/revert")
    assert r.status_code == 403


def test_version_list_includes_uploaded_by_name(client, db):
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value, full_name="Vera Version")
    _auth(admin)
    up = _upload(client, p.id, document_type="nda").json()
    rows = client.get(f"/partners/{p.id}/documents/{up['id']}/versions").json()
    assert len(rows) == 1
    assert rows[0]["uploaded_by_name"] == "Vera Version"


# ============================================================
# S3 -- partner attach proof + mark accepted (AD-35)
# ============================================================


def _sent_quote(db, partner):
    cm = _user(db, UserRole.channel_manager.value)
    deal = DealRegistration(id=uuid.uuid4(), partner_org_id=partner.id,
                            status="approved", customer_name="C", deal_name="D")
    db.add(deal); db.commit()
    q = Quote(id=uuid.uuid4(), deal_id=deal.id, partner_org_id=partner.id,
              created_by=cm.id, status="sent", currency_code="USD", active_version=1)
    db.add(q); db.commit()
    return q


def _attach_acceptance(db, partner, quote, uploader_id):
    doc = PartnerDocument(
        id=uuid.uuid4(), partner_org_id=partner.id,
        document_type="quote_acceptance", document_name="signed.pdf",
        file_size_bytes=14, mime_type="application/pdf",
        uploaded_by_user_id=uploader_id, status=DocumentStatus.pending_review,
        current_version_number=1, version_count=1,
    )
    db.add(doc); db.flush()
    db.add(DocumentReference(id=uuid.uuid4(), document_id=doc.id,
                             entity_type="quote", entity_id=quote.id,
                             label="quote_acceptance"))
    db.commit()
    return doc


def test_partner_admin_accepts_own_quote_with_attachment(client, db):
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    q = _sent_quote(db, p)
    _attach_acceptance(db, p, q, pa.id)
    _auth(pa)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"


def test_partner_user_accepts_own_quote_with_attachment(client, db):
    p = _partner(db)
    pu = _user(db, UserRole.partner_user.value, partner_org_id=p.id)
    q = _sent_quote(db, p)
    _attach_acceptance(db, p, q, pu.id)
    _auth(pu)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text


def test_partner_accept_without_attachment_returns_422(client, db):
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    q = _sent_quote(db, p)
    _auth(pa)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "accepted"})
    assert r.status_code == 422


def test_partner_cannot_accept_other_org_quote(client, db):
    p_a = _partner(db, "A")
    pa_owner = _user(db, UserRole.partner_admin.value, partner_org_id=p_a.id)
    q = _sent_quote(db, p_a)
    _attach_acceptance(db, p_a, q, pa_owner.id)
    pa_b = _user(db, UserRole.partner_admin.value, partner_org_id=_partner(db, "B").id)
    _auth(pa_b)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "accepted"})
    assert r.status_code == 403


def test_partner_cannot_retract_accepted_quote(client, db):
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    q = _sent_quote(db, p)
    q.status = "accepted"
    db.commit()
    _auth(pa)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "sent"})
    assert r.status_code == 403


def test_partner_cannot_mark_sent_or_expired(client, db):
    """Partners may ONLY do sent -> accepted, nothing else."""
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    q = _sent_quote(db, p)
    _auth(pa)
    r = client.patch(f"/quotes/{q.id}/status", json={"status": "expired"})
    assert r.status_code == 403
