"""Tests for backend/activation.py and partner activation endpoints (FPRM-107 / Sprint 7)."""
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
import models  # noqa: F401  registers all models
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
from activation import recalculate_activation


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_activation.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_activation.db"):
        try:
            os.remove("./test_activation.db")
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


def _override(db_session, user=None):
    def _db_dep():
        yield db_session
    app.dependency_overrides[get_db] = _db_dep
    if user is not None:
        def _user_dep():
            return user
        app.dependency_overrides[get_current_user] = _user_dep


def _make_partner(db, **kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        legal_name="Activation Co",
        program_type="distributor",
        partner_category="reseller",
        status="active",
        monthly_fee_status="current",
    )
    defaults.update(kwargs)
    partner = PartnerOrganization(**defaults)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def _make_profile(db, partner_org_id, pct=0, **kwargs):
    defaults = dict(id=uuid.uuid4(), partner_org_id=partner_org_id, profile_completeness_pct=pct)
    defaults.update(kwargs)
    profile = PartnerProfile(**defaults)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _make_approved_doc(db, partner_org_id, doc_type, uploaded_by_user_id):
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        document_type=doc_type,
        document_name=f"{doc_type.value}.pdf",
        file_path="/tmp/foo",
        uploaded_by_user_id=uploaded_by_user_id,
        status=DocumentStatus.approved,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


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


# ---- recalculate_activation unit tests ----


def test_recalculate_creates_checklist_when_missing(db_session):
    partner = _make_partner(db_session)
    assert (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=partner.id).first() is None
    )
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.partner_org_id == partner.id


def test_recalculate_sets_profile_complete_when_pct_gte_80(db_session):
    partner = _make_partner(db_session)
    _make_profile(db_session, partner.id, pct=82)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is True


def test_recalculate_profile_complete_false_below_threshold(db_session):
    partner = _make_partner(db_session)
    _make_profile(db_session, partner.id, pct=70)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is False


def test_recalculate_documents_uploaded_when_required_types_approved(db_session):
    partner = _make_partner(db_session)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    _make_approved_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    _make_approved_doc(db_session, partner.id, DocumentType.id_legal_representative, uploader.id)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.documents_uploaded is True


def test_recalculate_documents_uploaded_false_with_no_approved_docs(db_session):
    """FPRM-156: at least one approved document flips documents_uploaded True."""
    partner = _make_partner(db_session)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.documents_uploaded is False


def test_recalculate_documents_uploaded_true_with_one_approved_doc(db_session):
    """FPRM-156: single approved doc is sufficient (rule simplified after FPRM-144)."""
    partner = _make_partner(db_session)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    _make_approved_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.documents_uploaded is True


def test_recalculate_terms_signed_when_contract_start_date_present(db_session):
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.terms_signed is True


def test_recalculate_terms_signed_false_without_contract_date(db_session):
    partner = _make_partner(db_session)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.terms_signed is False


def test_recalculate_baseline_training_preserved_and_blocks_activation(db_session):
    """FPRM-145: baseline_training_complete is no longer hardcoded False.

    All three other gates True is no longer sufficient — training must also
    be true (set via POST /partners/{id}/activation/training-complete).
    """
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    _make_profile(db_session, partner.id, pct=100)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    _make_approved_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    _make_approved_doc(db_session, partner.id, DocumentType.id_legal_representative, uploader.id)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is True
    assert checklist.documents_uploaded is True
    assert checklist.terms_signed is True
    assert checklist.baseline_training_complete is False
    assert checklist.activation_complete is False  # now gated on training

    # Flip training True (simulating the endpoint), recalc → activation_complete True
    checklist.baseline_training_complete = True
    db_session.commit()
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is True


def test_activation_complete_only_true_when_all_three_required_true(db_session):
    partner = _make_partner(db_session)  # no contract_start_date
    _make_profile(db_session, partner.id, pct=100)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is True
    assert checklist.terms_signed is False
    assert checklist.activation_complete is False


def test_recalculate_sets_activated_at_on_first_complete(db_session):
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    _make_profile(db_session, partner.id, pct=100)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    _make_approved_doc(db_session, partner.id, DocumentType.fiscal_id, uploader.id)
    _make_approved_doc(db_session, partner.id, DocumentType.id_legal_representative, uploader.id)
    # FPRM-145: training must be set True before activation_complete can flip
    checklist = recalculate_activation(db_session, partner.id)
    checklist.baseline_training_complete = True
    db_session.commit()
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is True
    assert checklist.activated_at is not None


# ---- endpoint tests ----


def test_get_activation_as_partner_admin_own_org(db_session):
    partner = _make_partner(db_session)
    _make_profile(db_session, partner.id, pct=50)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["partner_org_id"] == str(partner.id)
    assert body["profile_complete"] is False
    assert body["activation_complete"] is False


def test_get_activation_partner_other_org_denied(db_session):
    partner_a = _make_partner(db_session, legal_name="A")
    partner_b = _make_partner(db_session, legal_name="B")
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner_a.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner_b.id}/activation")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


def test_get_activation_auto_initialises_if_missing(db_session):
    partner = _make_partner(db_session)
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    checklist = (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=partner.id).first()
    )
    assert checklist is not None


def test_post_activation_recalculate_internal_only(db_session):
    partner = _make_partner(db_session)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(f"/partners/{partner.id}/activation/recalculate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


def test_post_activation_recalculate_as_channel_manager(db_session):
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    _make_profile(db_session, partner.id, pct=100)
    user = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.post(f"/partners/{partner.id}/activation/recalculate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["profile_complete"] is True
    assert body["terms_signed"] is True
