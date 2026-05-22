"""Quote-document endpoints and the acceptance-doc gate on quote status.

Spec coverage:
* Upload document → stored with the correct base64 payload
* GET /quotes/{id}/documents returns list WITHOUT file_data
* Download returns binary with Content-Type + Content-Disposition headers
* File too large → 422
* Mark as accepted without a quote_acceptance document → 422
* Mark as accepted WITH a quote_acceptance document → 200
* partner_admin can GET and download own quote's documents
* partner_admin cannot upload documents (403)
* system_admin can delete a document; audit event logged
* channel_manager cannot delete a document (403)
* PDF bytes survive round-trip — magic bytes %PDF on decoded data
"""
import base64
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    AuditLog,
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    QuoteDocument,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


DB_PATH = "./test_quote_documents.db"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        _seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "quote_documents",
            "quote_line_items", "quote_versions", "quotes",
            "addon_catalog_items", "volume_discount_tiers", "feature_plan_prices",
            "deal_registrations", "users", "partner_organizations", "audit_log",
        ):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db_session):
    def _override_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_pricing(db):
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter", feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise", feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1, max_users=10, transactional_user_discount_pct=Decimal("0"), limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11, max_users=50, transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51, max_users=100, transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300, transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500, transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    db.commit()


def _org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:4]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(o); db.commit()
    return o


def _deal(db, org_id):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status="approved",
        customer_name="C", deal_name=f"D-{uuid.uuid4().hex[:4]}",
        estimated_deal_value=Decimal("10000.00"),
    )
    db.add(d); db.commit()
    return d


def _user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _make_quote(client, deal_id):
    r = client.post(f"/deals/{deal_id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# Minimal valid PDF (5-byte preamble + EOF marker is enough for our purposes).
_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n%%EOF\n"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode()


def _upload(client, quote_id, *, document_type="quote_acceptance",
            file_name="acceptance.pdf", bytes_payload=_PDF_BYTES, notes=None):
    payload = {
        "document_type": document_type,
        "file_name": file_name,
        "file_data": base64.b64encode(bytes_payload).decode(),
        "file_size_bytes": len(bytes_payload),
    }
    if notes is not None:
        payload["notes"] = notes
    return client.post(f"/quotes/{quote_id}/documents", json=payload)


# ============================================================
# Upload
# ============================================================


def test_upload_document_stores_base64_payload(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    r = _upload(client, qid, notes="Customer signed via email")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["document_type"] == "quote_acceptance"
    assert body["file_name"] == "acceptance.pdf"
    assert body["file_size_bytes"] == len(_PDF_BYTES)
    assert body["notes"] == "Customer signed via email"
    assert "file_data" not in body
    # Row persisted with the exact base64 we sent.
    row = db_session.query(QuoteDocument).filter(QuoteDocument.id == uuid.UUID(body["id"])).first()
    assert row is not None
    assert row.file_data == _PDF_B64


def test_list_documents_excludes_file_data(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    _upload(client, qid)
    r = client.get(f"/quotes/{qid}/documents")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert "file_data" not in rows[0]
    assert rows[0]["document_type"] == "quote_acceptance"


def test_upload_rejects_oversized_declared_size(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    # Use a tiny actual payload but lie about the size — still 422.
    r = client.post(f"/quotes/{qid}/documents", json={
        "document_type": "other",
        "file_name": "big.bin",
        "file_data": base64.b64encode(b"x").decode(),
        "file_size_bytes": 11 * 1024 * 1024,
    })
    assert r.status_code == 422
    assert "10 MB" in r.json()["detail"]


def test_upload_rejects_invalid_document_type(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    r = client.post(f"/quotes/{qid}/documents", json={
        "document_type": "not_a_real_type",
        "file_name": "x.pdf",
        "file_data": _PDF_B64,
        "file_size_bytes": len(_PDF_BYTES),
    })
    assert r.status_code == 422


def test_partner_admin_cannot_upload_document(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, deal.id)
    # Now switch to partner_admin and try to upload.
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = _upload(client, qid)
    assert r.status_code == 403


# ============================================================
# Download
# ============================================================


def test_download_returns_binary_with_attachment_headers(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    doc_id = _upload(client, qid).json()["id"]

    r = client.get(f"/quotes/{qid}/documents/{doc_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert 'attachment; filename="acceptance.pdf"' in r.headers["content-disposition"]
    # Round-trip the bytes — PDF magic must survive base64 encode + decode.
    assert r.content.startswith(b"%PDF")
    assert r.content == _PDF_BYTES


def test_partner_admin_can_list_and_download_own_quote_documents(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, deal.id)
    doc_id = _upload(client, qid).json()["id"]

    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r_list = client.get(f"/quotes/{qid}/documents")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1
    r_dl = client.get(f"/quotes/{qid}/documents/{doc_id}/download")
    assert r_dl.status_code == 200
    assert r_dl.content == _PDF_BYTES


# ============================================================
# Acceptance gate
# ============================================================


def test_cannot_mark_quote_accepted_without_acceptance_document(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    # No documents attached at all.
    r = client.patch(f"/quotes/{qid}/status", json={"status": "accepted"})
    assert r.status_code == 422
    assert "Proof of quote acceptance" in r.json()["detail"]

    # Other doc types do NOT satisfy the gate.
    _upload(client, qid, document_type="purchase_order", file_name="po.pdf")
    r2 = client.patch(f"/quotes/{qid}/status", json={"status": "accepted"})
    assert r2.status_code == 422


def test_can_mark_quote_accepted_with_acceptance_document(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    _upload(client, qid, document_type="quote_acceptance", file_name="signed.pdf")
    r = client.patch(f"/quotes/{qid}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"


# ============================================================
# Delete
# ============================================================


def test_system_admin_can_delete_document_and_audit_logged(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    doc_id = _upload(client, qid).json()["id"]

    _auth(_user(db_session, UserRole.system_admin.value))
    r = client.delete(f"/quotes/{qid}/documents/{doc_id}")
    assert r.status_code == 200, r.text
    assert client.get(f"/quotes/{qid}/documents").json() == []
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "quote.document_deleted")
        .filter(AuditLog.object_id == uuid.UUID(doc_id))
        .first()
    )
    assert audit is not None
    assert audit.before_state["file_name"] == "acceptance.pdf"


def test_channel_manager_cannot_delete_document(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    doc_id = _upload(client, qid).json()["id"]
    # Channel manager uploaded — now try to delete with the same role.
    r = client.delete(f"/quotes/{qid}/documents/{doc_id}")
    assert r.status_code == 403


# ============================================================
# Magic bytes survive the round-trip
# ============================================================


def test_pdf_magic_bytes_preserved_through_base64_round_trip(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    pdf_payload = b"%PDF-1.7\nbody\n%%EOF"
    r = _upload(client, qid, file_name="proof.pdf", bytes_payload=pdf_payload)
    doc_id = r.json()["id"]

    dl = client.get(f"/quotes/{qid}/documents/{doc_id}/download")
    assert dl.status_code == 200
    assert dl.content[:5] == b"%PDF-"
    assert dl.content == pdf_payload
