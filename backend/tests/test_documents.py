"""Tests for documents router (FPRM-55)."""
import os
import sys
import uuid
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    AuditLog,
    DocumentStatus,
    DocumentType,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_documents.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_documents.db"):
        try:
            os.remove("./test_documents.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user(role: UserRole, partner_org_id: uuid.UUID | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def make_partner(legal_name="Doc Test Co") -> PartnerOrganization:
    return PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=legal_name,
        program_type="distributor",
        partner_category="master",
        status="active",
        monthly_fee_status="current",
    )


def override(db_session, user):
    def _db():
        yield db_session
    def _user():
        return user
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user


def clear():
    app.dependency_overrides.clear()


def test_upload_document_as_partner_admin(db_session):
    partner = make_partner("Upload Co")
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.partner_admin, partner.id)
    db_session.add(user)
    db_session.commit()

    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/documents",
            json={
                "document_type": "nda",
                "document_name": "NDA-2026.pdf",
                "file_path": "/uploads/abc.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": 12345,
            },
        )
    finally:
        clear()
    assert r.status_code == 201
    data = r.json()
    assert data["document_type"] == "nda"
    # FPRM-384: with no document_type_rules row for 'nda', the upload
    # defaults to auto-approve (status=approved).
    assert data["status"] == "approved"


def test_upload_document_other_org_denied(db_session):
    p_a = make_partner("A")
    p_b = make_partner("B")
    db_session.add_all([p_a, p_b])
    db_session.commit()
    db_session.refresh(p_a)
    db_session.refresh(p_b)
    user = make_user(UserRole.partner_admin, p_a.id)
    db_session.add(user)
    db_session.commit()

    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{p_b.id}/documents",
            json={
                "document_type": "other",
                "document_name": "x.pdf",
                "file_path": "/x.pdf",
            },
        )
    finally:
        clear()
    assert r.status_code == 403


def test_upload_missing_required_fields(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()

    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/documents",
            json={"document_type": "nda"},
        )
    finally:
        clear()
    assert r.status_code == 422


def test_upload_proof_of_fiscal_domicile_too_old_rejected(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()

    old_date = (date.today() - timedelta(days=120)).isoformat()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/documents",
            json={
                "document_type": "proof_of_fiscal_domicile",
                "document_name": "constancia.pdf",
                "file_path": "/c.pdf",
                "expiry_date": old_date,
            },
        )
    finally:
        clear()
    assert r.status_code == 422
    assert "3 months" in r.json()["detail"]


def test_upload_proof_of_fiscal_domicile_current_accepted(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    user = make_user(UserRole.system_admin)
    db_session.add(user)
    db_session.commit()

    future = (date.today() + timedelta(days=60)).isoformat()
    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/documents",
            json={
                "document_type": "proof_of_fiscal_domicile",
                "document_name": "constancia.pdf",
                "file_path": "/c.pdf",
                "expiry_date": future,
            },
        )
    finally:
        clear()
    assert r.status_code == 201


def test_list_documents_as_partner_user(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    admin = make_user(UserRole.system_admin)
    db_session.add(admin)
    db_session.commit()
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        document_type=DocumentType.nda,
        document_name="x.pdf",
        file_path="/x",
        uploaded_by_user_id=admin.id,
    )
    db_session.add(doc)
    db_session.commit()
    user = make_user(UserRole.partner_user, partner.id)
    db_session.add(user)
    db_session.commit()

    override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/documents")
    finally:
        clear()
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_patch_document_status_internal_only(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    admin = make_user(UserRole.channel_ops_admin)
    db_session.add(admin)
    db_session.commit()
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        document_type=DocumentType.nda,
        document_name="x.pdf",
        file_path="/x",
        uploaded_by_user_id=admin.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/documents/{doc.id}",
            json={"status": "approved", "review_notes": "OK"},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["review_notes"] == "OK"
    db_session.refresh(doc)
    assert doc.reviewed_by_user_id is not None


def test_patch_document_denied_for_partner_admin(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    admin = make_user(UserRole.system_admin)
    db_session.add(admin)
    db_session.commit()
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        document_type=DocumentType.nda,
        document_name="x.pdf",
        file_path="/x",
        uploaded_by_user_id=admin.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    partner_admin = make_user(UserRole.partner_admin, partner.id)
    db_session.add(partner_admin)
    db_session.commit()

    override(db_session, partner_admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/documents/{doc.id}",
            json={"status": "approved"},
        )
    finally:
        clear()
    assert r.status_code == 403


def test_patch_document_status_change_audited(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    admin = make_user(UserRole.channel_ops_admin)
    db_session.add(admin)
    db_session.commit()
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        document_type=DocumentType.nda,
        document_name="x.pdf",
        file_path="/x",
        uploaded_by_user_id=admin.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    override(db_session, admin)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/documents/{doc.id}",
            json={"status": "rejected", "review_notes": "Bad scan"},
        )
    finally:
        clear()
    assert r.status_code == 200
    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.object_id == doc.id, AuditLog.action == "partner_document.status_change")
        .all()
    )
    assert len(entries) >= 1


def test_document_models_importable():
    from models import DocumentType, DocumentStatus, PartnerDocument
    assert DocumentType.proof_of_fiscal_domicile.value == "proof_of_fiscal_domicile"
    assert DocumentStatus.pending_review.value == "pending_review"
    assert PartnerDocument.__tablename__ == "partner_documents"
