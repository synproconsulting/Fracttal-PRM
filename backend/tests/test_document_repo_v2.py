"""Sprint 22 / Document Repository v2 -- versioning, rules, preview,
self-service delete, uploaded_by_name.

Covers the 20+ test cases listed across Story 2 + Story 3 in the
sprint spec, plus migration importability guards for 037/038.
"""
import base64
import importlib.util
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    AuditLog,
    DocumentReference,
    DocumentStatus,
    DocumentTypeRule,
    DocumentVersion,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import UserRole


_PDF_BYTES = b"%PDF-1.4\n%%EOF"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode()
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
            "document_versions",
            "document_references",
            "partner_documents",
            "document_type_rules",
            "audit_log",
            "users",
            "partner_organizations",
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
        id=uuid.uuid4(),
        legal_name=f"{name} {uuid.uuid4().hex[:4]}",
        program_type="distributor",
        partner_category="reseller",
        status="active",
    )
    db.add(p); db.commit()
    return p


def _user(db, role, partner_org_id=None, full_name=None):
    u = User(
        id=uuid.uuid4(),
        email=f"{role}-{uuid.uuid4().hex[:6]}@t",
        hashed_password="x",
        role=role,
        is_active=True,
        partner_org_id=partner_org_id,
        full_name=full_name,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _seed_quote_acceptance_rule(db):
    """Mirrors migration 038's seed row -- needed for sqlite test paths
    where the migration backfill doesn't run."""
    if db.query(DocumentTypeRule).filter(
        DocumentTypeRule.document_type == "quote_acceptance"
    ).first() is None:
        db.add(DocumentTypeRule(
            id=uuid.uuid4(),
            document_type="quote_acceptance",
            requires_approval=False,
            auto_approve=True,
            description="seed",
        ))
        db.commit()


def _seed_contract_rule(db):
    if db.query(DocumentTypeRule).filter(
        DocumentTypeRule.document_type == "contract"
    ).first() is None:
        db.add(DocumentTypeRule(
            id=uuid.uuid4(),
            document_type="contract",
            requires_approval=True,
            auto_approve=False,
            description="seed",
        ))
        db.commit()


def _upload(client, partner_id, document_type="nda", document_name="x.pdf",
            payload_bytes=_PDF_BYTES, mime_type="application/pdf"):
    return client.post(
        f"/partners/{partner_id}/documents",
        json={
            "document_type": document_type,
            "document_name": document_name,
            "file_data": base64.b64encode(payload_bytes).decode(),
            "file_size_bytes": len(payload_bytes),
            "mime_type": mime_type,
        },
    )


# ============================================================
# Story 2 -- upload writes to document_versions + auto_approve
# ============================================================


def test_upload_creates_version_1_in_document_versions(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = _upload(client, p.id, document_type="nda")
    assert r.status_code == 201, r.text
    doc_id = uuid.UUID(r.json()["id"])
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].is_current is True
    assert versions[0].file_data == _PDF_B64
    # AD-34: partner_documents.file_data must NOT carry the bytes
    doc = db.query(PartnerDocument).filter(PartnerDocument.id == doc_id).first()
    assert doc.file_data is None
    assert doc.current_version_number == 1
    assert doc.version_count == 1


def test_upload_auto_approve_rule_sets_status_approved(client, db):
    p = _partner(db)
    _seed_quote_acceptance_rule(db)
    _auth(_user(db, UserRole.channel_manager.value))
    r = _upload(client, p.id, document_type="quote_acceptance")
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(r.json()["id"])
    ).first()
    assert doc.status == DocumentStatus.approved


def test_upload_no_rule_defaults_to_approved(client, db):
    """FPRM-384: with no document_type_rules row, the default is
    auto-approve (status=approved)."""
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = _upload(client, p.id, document_type="nda")
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(r.json()["id"])
    ).first()
    assert doc.status == DocumentStatus.approved


def test_upload_requires_approval_rule_sets_status_pending(client, db):
    """FPRM-384: a rule with requires_approval=true (auto_approve=false)
    makes the upload land in pending_review."""
    p = _partner(db)
    _seed_contract_rule(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = _upload(client, p.id, document_type="contract")
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(r.json()["id"])
    ).first()
    assert doc.status == DocumentStatus.pending_review


def test_upload_matches_rule_case_insensitively(client, db):
    """FPRM-386 regression: a rule persisted with different casing ("NDA")
    than the upload's canonical document_type ("nda") is still matched, so
    requires_approval is honoured instead of silently auto-approving. This
    is the exact production failure -- the free-text Document Rules form
    stored "NDA" while uploads send the lowercase code."""
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    db.add(DocumentTypeRule(
        id=uuid.uuid4(),
        document_type="NDA",  # uppercase, as a free-text rule entry stores it
        requires_approval=True,
        auto_approve=False,
    ))
    db.commit()
    r = _upload(client, p.id, document_type="nda")  # canonical lowercase code
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(r.json()["id"])
    ).first()
    assert doc.status == DocumentStatus.pending_review


def test_upload_matches_rule_ignoring_whitespace(client, db):
    """FPRM-386: surrounding whitespace on the stored rule type is ignored."""
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    db.add(DocumentTypeRule(
        id=uuid.uuid4(),
        document_type="  contract  ",
        requires_approval=True,
        auto_approve=False,
    ))
    db.commit()
    r = _upload(client, p.id, document_type="contract")
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(r.json()["id"])
    ).first()
    assert doc.status == DocumentStatus.pending_review


def test_rule_create_duplicate_is_case_insensitive(client, db):
    """FPRM-386: cannot create "nda" when "NDA" already exists -- otherwise
    case-insensitive upload matching would be ambiguous about which wins."""
    _auth(_user(db, UserRole.system_admin.value))
    r1 = client.post("/admin/document-type-rules",
                     json={"document_type": "NDA", "requires_approval": True})
    assert r1.status_code == 201
    r2 = client.post("/admin/document-type-rules",
                     json={"document_type": "nda", "requires_approval": True})
    assert r2.status_code == 409


# ============================================================
# Story 2 -- new version endpoint
# ============================================================


def test_upload_new_version_increments_version_count(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.channel_manager.value))
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = upload["id"]
    r = client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2),
              "mime_type": "application/pdf"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["current_version_number"] == 2
    assert body["version_count"] == 2


def test_upload_new_version_marks_previous_not_current(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.channel_manager.value))
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = uuid.UUID(upload["id"])
    client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)},
    )
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(DocumentVersion.version_number).all()
    assert [v.is_current for v in versions] == [False, True]


def test_upload_new_version_resets_status_if_requires_approval(client, db):
    p = _partner(db)
    _seed_contract_rule(db)
    admin = _user(db, UserRole.system_admin.value)
    _auth(admin)
    upload = _upload(client, p.id, document_type="contract").json()
    doc_id = upload["id"]
    # Approve the initial version
    client.patch(
        f"/partners/{p.id}/documents/{doc_id}",
        json={"status": "approved"},
    )
    # Upload v2; should reset to pending_review
    r = client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)},
    )
    assert r.status_code == 201, r.text
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == uuid.UUID(doc_id)
    ).first()
    assert doc.status == DocumentStatus.pending_review


def test_list_versions_excludes_file_data(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.channel_manager.value))
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = upload["id"]
    client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)},
    )
    r = client.get(f"/partners/{p.id}/documents/{doc_id}/versions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    # Newest first
    assert rows[0]["version_number"] == 2
    assert rows[1]["version_number"] == 1
    for row in rows:
        assert "file_data" not in row


def test_download_specific_version_returns_correct_bytes(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.channel_manager.value))
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = upload["id"]
    r2 = client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2),
              "mime_type": "application/pdf"},
    )
    assert r2.status_code == 201
    versions_resp = client.get(f"/partners/{p.id}/documents/{doc_id}/versions").json()
    v1 = next(v for v in versions_resp if v["version_number"] == 1)
    v2 = next(v for v in versions_resp if v["version_number"] == 2)
    r_v1 = client.get(f"/partners/{p.id}/documents/{doc_id}/versions/{v1['id']}/download")
    assert r_v1.status_code == 200
    assert r_v1.content == _PDF_BYTES
    r_v2 = client.get(f"/partners/{p.id}/documents/{doc_id}/versions/{v2['id']}/download")
    assert r_v2.status_code == 200
    assert r_v2.content == _PDF_V2


def test_revert_sets_is_current_on_target_version(client, db):
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = upload["id"]
    client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)},
    )
    versions = client.get(f"/partners/{p.id}/documents/{doc_id}/versions").json()
    v1 = next(v for v in versions if v["version_number"] == 1)
    r = client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions/{v1['id']}/revert",
    )
    assert r.status_code == 200, r.text
    assert r.json()["current_version_number"] == 1
    versions_after = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == uuid.UUID(doc_id)
    ).order_by(DocumentVersion.version_number).all()
    assert [v.is_current for v in versions_after] == [True, False]


def test_revert_as_partner_admin_own_org_succeeds(client, db):
    """FPRM-390 / AD-36 supersedes the Sprint 22 internal-only rule:
    partner_admin may now revert versions of their OWN org's documents."""
    p = _partner(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(cm)
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = upload["id"]
    client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions",
        json={"file_data": _PDF_V2_B64, "file_size_bytes": len(_PDF_V2)},
    )
    versions = client.get(f"/partners/{p.id}/documents/{doc_id}/versions").json()
    v1 = next(v for v in versions if v["version_number"] == 1)
    # Switch to partner_admin of the SAME org
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    _auth(pa)
    r = client.post(
        f"/partners/{p.id}/documents/{doc_id}/versions/{v1['id']}/revert",
    )
    assert r.status_code == 200, r.text
    assert r.json()["current_version_number"] == 1


# ============================================================
# Story 2 -- document_type_rules CRUD
# ============================================================


def test_document_type_rule_create_read_update_delete(client, db):
    _auth(_user(db, UserRole.system_admin.value))
    # Create
    r = client.post(
        "/admin/document-type-rules",
        json={"document_type": "nda", "requires_approval": True,
              "auto_approve": False, "description": "NDA docs"},
    )
    assert r.status_code == 201
    rule_id = r.json()["id"]
    # Read
    r = client.get("/admin/document-type-rules")
    assert r.status_code == 200
    types = [row["document_type"] for row in r.json()]
    assert "nda" in types
    # Update
    r = client.patch(
        f"/admin/document-type-rules/{rule_id}",
        json={"description": "Updated"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Updated"
    # Delete (no partner_documents use this type yet)
    r = client.delete(f"/admin/document-type-rules/{rule_id}")
    assert r.status_code == 204


def test_document_type_rule_delete_in_use_succeeds(client, db):
    """FPRM-385: rules are freely deletable even when partner_documents of
    that type exist. The documents keep their current status (no cascade)."""
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value)
    _auth(admin)
    create = client.post(
        "/admin/document-type-rules",
        json={"document_type": "custom_type", "requires_approval": True},
    )
    rule_id = create.json()["id"]
    # Create a partner_document with this type
    upload = _upload(client, p.id, document_type="custom_type", document_name="x.pdf")
    doc_id = uuid.UUID(upload.json()["id"])
    doc_before = db.query(PartnerDocument).filter(
        PartnerDocument.id == doc_id
    ).first()
    status_before = doc_before.status
    # Delete now succeeds (guard removed)
    r = client.delete(f"/admin/document-type-rules/{rule_id}")
    assert r.status_code == 204
    # Rule gone
    assert db.query(DocumentTypeRule).filter(
        DocumentTypeRule.id == uuid.UUID(rule_id)
    ).first() is None
    # Document survives unchanged
    doc_after = db.query(PartnerDocument).filter(
        PartnerDocument.id == doc_id
    ).first()
    assert doc_after is not None
    assert doc_after.status == status_before


def test_document_type_rule_auto_approve_forces_no_manual_approval(client, db):
    _auth(_user(db, UserRole.system_admin.value))
    r = client.post(
        "/admin/document-type-rules",
        json={"document_type": "demo_x", "requires_approval": True,
              "auto_approve": True},
    )
    assert r.status_code == 201
    # auto_approve=True must force requires_approval=False per spec
    assert r.json()["auto_approve"] is True
    assert r.json()["requires_approval"] is False


# ============================================================
# Story 2 -- acceptance gate with rule
# ============================================================


def _build_quote(db):
    """Minimal quote + version setup so the acceptance gate can run."""
    from models import Quote, QuoteVersion, DealRegistration, FeaturePlanPrice
    from decimal import Decimal
    from datetime import date
    p = _partner(db, name="Q")
    cm = _user(db, UserRole.channel_manager.value)
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter", feature_pack_annual=Decimal("1161"),
                         transactional_user_annual=Decimal("540"),
                         limited_tech_user_annual=Decimal("240"),
                         effective_from=today),
    ])
    db.commit()
    deal = DealRegistration(
        id=uuid.uuid4(), partner_org_id=p.id, status="approved",
        customer_name="C", deal_name="D",
        estimated_deal_value=Decimal("1000"),
    )
    db.add(deal); db.commit()
    quote = Quote(
        id=uuid.uuid4(), deal_id=deal.id, partner_org_id=p.id,
        created_by=cm.id, status="sent", currency_code="USD",
        active_version=1,
    )
    db.add(quote)
    qv = QuoteVersion(
        id=uuid.uuid4(), quote_id=quote.id, version_number=1,
        feature_plan="starter", feature_plan_discount_pct=Decimal("0"),
        qty_transactional_users=1, qty_limited_tech_users=0,
        grand_total_before_discount=Decimal("1701"),
        grand_total_after_discount=Decimal("1701"),
    )
    db.add(qv); db.commit()
    return p, deal, quote, cm


def _seed_doc_and_reference(db, partner_id, quote_id, uploaded_by_id,
                              status=DocumentStatus.pending_review):
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        document_type="quote_acceptance",
        document_name="evidence.pdf",
        file_size_bytes=14,
        mime_type="application/pdf",
        uploaded_by_user_id=uploaded_by_id,
        status=status,
        current_version_number=1,
        version_count=1,
    )
    db.add(doc); db.flush()
    db.add(DocumentVersion(
        id=uuid.uuid4(), document_id=doc.id, version_number=1,
        file_data=_PDF_B64, file_size_bytes=14,
        mime_type="application/pdf",
        uploaded_by=uploaded_by_id, is_current=True,
    ))
    db.add(DocumentReference(
        id=uuid.uuid4(), document_id=doc.id, entity_type="quote",
        entity_id=quote_id, label="quote_acceptance",
    ))
    db.commit()
    return doc


def test_acceptance_gate_with_requires_approval_false(client, db):
    """quote_acceptance seed has requires_approval=false -- a pending
    document attached via reference satisfies the gate."""
    p, deal, quote, cm = _build_quote(db)
    _seed_quote_acceptance_rule(db)
    _seed_doc_and_reference(db, p.id, quote.id, cm.id,
                              status=DocumentStatus.pending_review)
    _auth(cm)
    r = client.patch(f"/quotes/{quote.id}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text


def test_acceptance_gate_with_requires_approval_true(client, db):
    """If admin flips quote_acceptance to requires_approval=true, the
    pending document no longer satisfies the gate."""
    p, deal, quote, cm = _build_quote(db)
    db.add(DocumentTypeRule(
        id=uuid.uuid4(),
        document_type="quote_acceptance",
        requires_approval=True,
        auto_approve=False,
    ))
    _seed_doc_and_reference(db, p.id, quote.id, cm.id,
                              status=DocumentStatus.pending_review)
    db.commit()
    _auth(cm)
    r = client.patch(f"/quotes/{quote.id}/status", json={"status": "accepted"})
    assert r.status_code == 422


# ============================================================
# Story 3 -- preview, self-service delete, uploaded_by_name
# ============================================================


def test_preview_pdf_returns_inline_disposition(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    upload = _upload(client, p.id, document_type="nda",
                     mime_type="application/pdf").json()
    r = client.get(f"/partners/{p.id}/documents/{upload['id']}/preview")
    assert r.status_code == 200
    assert "inline" in r.headers["content-disposition"]
    assert r.headers["content-type"].startswith("application/pdf")


def test_preview_unknown_type_returns_attachment_disposition(client, db):
    p = _partner(db)
    _auth(_user(db, UserRole.system_admin.value))
    upload = _upload(client, p.id, document_type="nda",
                     mime_type="application/zip").json()
    r = client.get(f"/partners/{p.id}/documents/{upload['id']}/preview")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]


def test_partner_admin_delete_unreferenced_succeeds(client, db):
    """FPRM-383: an unreferenced document is permanently removed from the
    DB (was previously soft-flagged as rejected). The version rows cascade
    away too."""
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    _auth(pa)
    upload = _upload(client, p.id, document_type="nda").json()
    doc_id = uuid.UUID(upload["id"])
    r = client.delete(f"/partners/{p.id}/documents/{upload['id']}")
    assert r.status_code == 200
    # Permanent delete: row is gone
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == doc_id
    ).first()
    assert doc is None
    # Version rows cascaded away
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).all()
    assert versions == []


def test_partner_admin_delete_referenced_returns_409(client, db):
    p = _partner(db)
    pa = _user(db, UserRole.partner_admin.value, partner_org_id=p.id)
    _auth(pa)
    upload = _upload(client, p.id, document_type="nda").json()
    # Create a reference linking it to a fake quote
    fake_quote_id = uuid.uuid4()
    client.post(
        f"/partners/{p.id}/documents/{upload['id']}/references",
        json={"entity_type": "quote", "entity_id": str(fake_quote_id),
              "label": "quote_acceptance"},
    )
    r = client.delete(f"/partners/{p.id}/documents/{upload['id']}")
    assert r.status_code == 409


def test_document_list_includes_uploaded_by_name(client, db):
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value, full_name="Alice Admin")
    _auth(admin)
    _upload(client, p.id, document_type="nda")
    r = client.get(f"/partners/{p.id}/documents")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["uploaded_by_name"] == "Alice Admin"


def test_document_list_falls_back_to_email_when_no_full_name(client, db):
    """When User.full_name is null, uploaded_by_name falls back to email."""
    p = _partner(db)
    admin = _user(db, UserRole.system_admin.value)  # no full_name
    _auth(admin)
    _upload(client, p.id, document_type="nda")
    items = client.get(f"/partners/{p.id}/documents").json()["items"]
    assert len(items) == 1
    assert items[0]["uploaded_by_name"] == admin.email


# ============================================================
# Migration importability
# ============================================================


@pytest.mark.parametrize("mod_name", [
    "alembic.versions.037_document_versions",
    "alembic.versions.038_document_type_rules",
])
def test_migration_modules_importable(mod_name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = mod_name.replace(".", "/") + ".py"
    full = os.path.join(here, rel)
    assert os.path.exists(full), f"missing migration: {full}"
    spec = importlib.util.spec_from_file_location(mod_name, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert hasattr(mod, "revision")


def test_document_versions_table_exists(engine):
    insp = inspect(engine)
    assert "document_versions" in set(insp.get_table_names())
    cols = {c["name"] for c in insp.get_columns("document_versions")}
    assert {"id", "document_id", "version_number", "file_data",
            "is_current", "uploaded_by", "uploaded_at"}.issubset(cols)


def test_document_type_rules_table_exists(engine):
    insp = inspect(engine)
    assert "document_type_rules" in set(insp.get_table_names())
