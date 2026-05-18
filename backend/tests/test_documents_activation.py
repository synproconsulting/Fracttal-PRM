"""Tests for FPRM-108 — document approval triggers activation recalc.

Lives in its own file so it does not collide with the established test_documents.py
fixtures.
"""
import os
import sys
import uuid
from datetime import date

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
    DocumentStatus,
    DocumentType,
    PartnerActivationChecklist,
    PartnerDocument,
    PartnerOrganization,
    PartnerProfile,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_documents_activation.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_documents_activation.db"):
        try:
            os.remove("./test_documents_activation.db")
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


def _make_partner(db, contract_start_date=None):
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name="Approval Co",
        program_type="distributor",
        partner_category="reseller",
        status="active",
        monthly_fee_status="current",
        contract_start_date=contract_start_date,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, role: UserRole, partner_org_id=None):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_pending_doc(db, partner_org_id, doc_type, uploader_id):
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        document_type=doc_type,
        document_name=f"{doc_type.value}.pdf",
        file_path="/tmp/x",
        uploaded_by_user_id=uploader_id,
        status=DocumentStatus.pending_review,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _override(db_session, user):
    def _db():
        yield db_session
    def _u():
        return user
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _u


def test_approving_a_single_doc_flips_checklist(db_session):
    """FPRM-156: any one approved document flips documents_uploaded True.

    Earlier rule required both fiscal_id and id_legal_representative; that
    broke once FPRM-144 made document_types admin-configurable so partners
    outside the original two-type list could never activate.
    """
    partner = _make_partner(db_session)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    uploader = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    doc = _make_pending_doc(db_session, partner.id, DocumentType.nda, uploader.id)

    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/documents/{doc.id}",
            json={"status": "approved"},
        )
        assert r.status_code == 200
        ck = (
            db_session.query(PartnerActivationChecklist)
            .filter_by(partner_org_id=partner.id).first()
        )
        assert ck.documents_uploaded is True
    finally:
        app.dependency_overrides.clear()


def test_documents_uploaded_regression_single_approved(db_session):
    """FPRM-156 regression: upload 1 document, approve it, call recalculate, assert documents_uploaded=True."""
    from activation import recalculate_activation
    partner = _make_partner(db_session)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    doc = _make_pending_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    doc.status = DocumentStatus.approved
    db_session.commit()

    ck = recalculate_activation(db_session, partner.id)
    assert ck.documents_uploaded is True


def test_rejecting_a_doc_does_not_flip_documents_uploaded(db_session):
    partner = _make_partner(db_session)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    uploader = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    doc = _make_pending_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)

    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/documents/{doc.id}",
            json={"status": "rejected", "review_notes": "Illegible scan"},
        )
        assert r.status_code == 200
    finally:
        app.dependency_overrides.clear()
    # No checklist row should have been auto-created by recalc since the approval
    # branch did not fire. (Rejection never calls recalculate_activation.)
    ck = (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=partner.id).first()
    )
    assert ck is None


def test_approving_full_set_triggers_activation_complete(db_session):
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    profile = PartnerProfile(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        profile_completeness_pct=95,
    )
    db_session.add(profile)
    db_session.commit()

    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    uploader = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    doc_fiscal = _make_pending_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    doc_id_legal = _make_pending_doc(db_session, partner.id, DocumentType.id_legal_representative, uploader.id)

    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        client.patch(f"/partners/{partner.id}/documents/{doc_fiscal.id}", json={"status": "approved"})
        client.patch(f"/partners/{partner.id}/documents/{doc_id_legal.id}", json={"status": "approved"})
    finally:
        app.dependency_overrides.clear()

    ck = (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=partner.id).first()
    )
    assert ck is not None
    assert ck.profile_complete is True
    assert ck.documents_uploaded is True
    assert ck.terms_signed is True
    # FPRM-145: training is also required for activation_complete now
    ck.baseline_training_complete = True
    db_session.commit()
    from activation import recalculate_activation
    ck = recalculate_activation(db_session, partner.id)
    assert ck.activation_complete is True
    assert ck.activated_at is not None
