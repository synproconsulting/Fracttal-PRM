"""Sprint 21 / AD-33 -- centralised partner documents API.

Covers the upload-with-file_data path, the tenant_org isolation boundary,
the new ``download`` / ``delete`` / ``references`` endpoints, and the
absence of ``file_data`` from every metadata response. The legacy
file_path upload path is exercised in test_documents.py and stays green.
"""
import base64
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
import models  # noqa: F401  ensure all models registered
from models import (
    AuditLog,
    DocumentReference,
    DocumentStatus,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import UserRole


_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n%%EOF\n"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode()


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
        s.rollback()
        for tbl in (
            "document_references",
            "partner_documents",
            "audit_log",
            "users",
            "partner_organizations",
        ):
            try:
                from sqlalchemy import text
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db):
    def _override_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _partner(db, name="Org"):
    p = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"{name} {uuid.uuid4().hex[:4]}",
        program_type="distributor",
        partner_category="reseller",
        status="active",
    )
    db.add(p)
    db.commit()
    return p


def _user(db, role, partner_org_id=None):
    u = User(
        id=uuid.uuid4(),
        email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x",
        role=role,
        is_active=True,
        partner_org_id=partner_org_id,
    )
    db.add(u)
    db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _upload(client, partner_id, *, document_type="quote_acceptance",
            document_name="acceptance.pdf", bytes_payload=_PDF_BYTES,
            mime_type="application/pdf"):
    return client.post(
        f"/partners/{partner_id}/documents",
        json={
            "document_type": document_type,
            "document_name": document_name,
            "file_data": base64.b64encode(bytes_payload).decode(),
            "file_size_bytes": len(bytes_payload),
            "mime_type": mime_type,
        },
    )


# ============================================================
# Upload path (centralised file_data flow)
# ============================================================


def test_upload_with_file_data_returns_201_no_file_data_in_body(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    r = _upload(client, p.id, document_type="nda")
    assert r.status_code == 201, r.text
    body = r.json()
    assert "file_data" not in body
    assert body["document_name"] == "acceptance.pdf"
    assert body["mime_type"] == "application/pdf"
    row = (
        db.query(PartnerDocument)
        .filter(PartnerDocument.id == uuid.UUID(str(body["id"])))
        .first()
    )
    assert row is not None
    # Sprint 22 / AD-34 -- file_data lives in document_versions now, not
    # on partner_documents.file_data (which stays NULL for new uploads).
    assert row.file_data is None
    from models import DocumentVersion
    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == row.id,
            DocumentVersion.is_current.is_(True),
        )
        .first()
    )
    assert version is not None
    assert version.file_data == _PDF_B64
    assert version.version_number == 1


def test_upload_with_quote_acceptance_type_accepted(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    r = _upload(client, p.id, document_type="quote_acceptance")
    assert r.status_code == 201, r.text
    assert r.json()["document_type"] == "quote_acceptance"


def test_upload_wrong_org_partner_admin_returns_403(client, db):
    p_a = _partner(db, "A")
    p_b = _partner(db, "B")
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p_a.id))
    r = _upload(client, p_b.id, document_type="nda")
    assert r.status_code == 403


def test_upload_file_exceeds_10mb_returns_422(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    # Declared size over 10 MB rejected even with tiny payload.
    r = client.post(
        f"/partners/{p.id}/documents",
        json={
            "document_type": "nda",
            "document_name": "x.bin",
            "file_data": base64.b64encode(b"x").decode(),
            "file_size_bytes": 11 * 1024 * 1024,
        },
    )
    assert r.status_code == 422
    assert "10 MB" in r.json()["detail"]


# ============================================================
# Listing -- never leaks file_data
# ============================================================


def test_list_documents_omits_file_data(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    _upload(client, p.id, document_type="nda")
    _upload(client, p.id, document_type="nda", document_name="another.pdf")
    r = client.get(f"/partners/{p.id}/documents")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    for item in items:
        assert "file_data" not in item


def test_list_documents_filters_by_status(client, db):
    p = _partner(db)
    admin = _user(db, UserRole.channel_ops_admin.value)
    _auth(admin)
    # FPRM-384: with no rule for 'nda', uploads auto-approve. The first
    # doc ("acceptance.pdf") stays approved; the second is explicitly
    # flipped to rejected so the approved-status filter excludes it.
    _upload(client, p.id, document_type="nda")
    upl2 = _upload(client, p.id, document_type="nda", document_name="rejected.pdf")
    client.patch(
        f"/partners/{p.id}/documents/{upl2.json()['id']}",
        json={"status": "rejected"},
    )

    r = client.get(f"/partners/{p.id}/documents?status=approved")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["document_name"] == "acceptance.pdf"


def test_list_documents_wrong_org_partner_admin_returns_403(client, db):
    p_a = _partner(db, "A")
    p_b = _partner(db, "B")
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p_a.id))
    r = client.get(f"/partners/{p_b.id}/documents")
    assert r.status_code == 403


# ============================================================
# Metadata -- single doc endpoint
# ============================================================


def test_get_document_metadata_omits_file_data(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    r = client.get(f"/partners/{p.id}/documents/{doc_id}")
    assert r.status_code == 200, r.text
    assert "file_data" not in r.json()


def test_get_document_metadata_wrong_org_404(client, db):
    p_a = _partner(db, "A")
    p_b = _partner(db, "B")
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p_a.id))
    # Seed a doc on p_b owned by an admin
    admin = _user(db, UserRole.system_admin.value)
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=p_b.id,
        document_type="nda",
        document_name="leak.pdf",
        file_data=_PDF_B64,
        uploaded_by_user_id=admin.id,
    )
    db.add(doc)
    db.commit()
    r = client.get(f"/partners/{p_a.id}/documents/{doc.id}")
    # 403 from the tenant guard (partner not allowed to look at p_b at all)
    # or 404 from the doc.partner_org_id mismatch -- either is acceptable
    # security behaviour; we just need not-200.
    assert r.status_code in (403, 404)


# ============================================================
# Download -- streams bytes with attachment header
# ============================================================


def test_download_returns_bytes_with_content_disposition(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p.id))
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    r = client.get(f"/partners/{p.id}/documents/{doc_id}/download")
    assert r.status_code == 200, r.text
    assert r.content == _PDF_BYTES
    assert 'attachment; filename="acceptance.pdf"' in r.headers["content-disposition"]


def test_download_wrong_org_partner_admin_returns_403(client, db):
    p_a = _partner(db, "A")
    p_b = _partner(db, "B")
    admin = _user(db, UserRole.system_admin.value)
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=p_b.id,
        document_type="nda",
        document_name="leak.pdf",
        file_data=_PDF_B64,
        uploaded_by_user_id=admin.id,
    )
    db.add(doc)
    db.commit()
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=p_a.id))
    r = client.get(f"/partners/{p_a.id}/documents/{doc.id}/download")
    assert r.status_code in (403, 404)


# ============================================================
# Review (PATCH) -- internal only
# ============================================================


def test_patch_status_as_channel_manager_returns_200(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    r = client.patch(
        f"/partners/{p.id}/documents/{doc_id}",
        json={"status": "approved", "review_notes": "ok"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_patch_status_as_partner_admin_returns_403(client, db):
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    _auth(pa)
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    r = client.patch(
        f"/partners/{p.id}/documents/{doc_id}",
        json={"status": "approved"},
    )
    assert r.status_code == 403


# ============================================================
# Delete -- system_admin / channel_ops_admin only
# ============================================================


def test_delete_as_system_admin_succeeds_and_audits(client, db):
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value)
    _auth(admin)
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    r = client.delete(f"/partners/{p.id}/documents/{doc_id}")
    assert r.status_code == 200
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "partner_document.deleted")
        .filter(AuditLog.object_id == uuid.UUID(doc_id))
        .first()
    )
    assert audit is not None


def test_delete_as_channel_manager_returns_403(client, db):
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value)
    _auth(admin)
    doc_id = _upload(client, p.id, document_type="nda").json()["id"]
    _auth(_user(db, UserRole.channel_manager.value))
    r = client.delete(f"/partners/{p.id}/documents/{doc_id}")
    assert r.status_code == 403


# ============================================================
# References sub-router
# ============================================================


def test_create_reference_links_document_to_quote(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    doc_id = _upload(client, p.id, document_type="quote_acceptance").json()["id"]
    quote_id = uuid.uuid4()
    r = client.post(
        f"/partners/{p.id}/documents/{doc_id}/references",
        json={
            "entity_type": "quote",
            "entity_id": str(quote_id),
            "label": "quote_acceptance",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["entity_type"] == "quote"
    assert r.json()["label"] == "quote_acceptance"

    refs = (
        db.query(DocumentReference)
        .filter(DocumentReference.document_id == uuid.UUID(doc_id))
        .all()
    )
    assert len(refs) == 1


def test_list_references_returns_existing_links(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    doc_id = _upload(client, p.id, document_type="quote_acceptance").json()["id"]
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    for qid in (q1, q2):
        client.post(
            f"/partners/{p.id}/documents/{doc_id}/references",
            json={"entity_type": "quote", "entity_id": str(qid),
                  "label": "quote_acceptance"},
        )
    r = client.get(f"/partners/{p.id}/documents/{doc_id}/references")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_delete_reference_removes_link_only(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    doc_id = _upload(client, p.id, document_type="quote_acceptance").json()["id"]
    q = uuid.uuid4()
    ref = client.post(
        f"/partners/{p.id}/documents/{doc_id}/references",
        json={"entity_type": "quote", "entity_id": str(q),
              "label": "quote_acceptance"},
    ).json()
    r = client.delete(
        f"/partners/{p.id}/documents/{doc_id}/references/{ref['id']}"
    )
    assert r.status_code == 200
    assert (
        db.query(PartnerDocument)
        .filter(PartnerDocument.id == uuid.UUID(doc_id))
        .first()
    ) is not None
    assert (
        db.query(DocumentReference)
        .filter(DocumentReference.id == uuid.UUID(ref["id"]))
        .first()
    ) is None
