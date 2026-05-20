"""Tests for FPRM-270 / Sprint 17 — dynamic activation enforcement.

Covers ``backend/activation.py`` (config-driven required-criteria evaluation
with fallback to the hardcoded four-flag rule) and the new
``GET /partners/{id}/activation/criteria`` endpoint.
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
    ActivationChecklistConfig,
    DocumentStatus,
    DocumentType,
    PartnerActivationChecklist,
    PartnerDocument,
    PartnerOrganization,
    PartnerProfile,
    User,
)
from roles import UserRole
from activation import (
    CRITERION_KEY_MAP,
    HARDCODED_REQUIRED_KEYS,
    recalculate_activation,
    resolve_required_criteria,
)


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_activation_dynamic.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_activation_dynamic.db"):
        try:
            os.remove("./test_activation_dynamic.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        # Clean activation config rows between tests so each test starts
        # from a known (empty) dynamic state.
        db.query(ActivationChecklistConfig).delete()
        db.commit()
        yield db
    finally:
        db.query(ActivationChecklistConfig).delete()
        db.commit()
        db.close()


def _override(db_session, user=None):
    def _db_dep():
        yield db_session
    app.dependency_overrides[get_db] = _db_dep
    if user is not None:
        def _user_dep():
            return user
        app.dependency_overrides[get_current_user] = _user_dep


def _make_partner(db, category="reseller", tier=None, **kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        legal_name=f"Activation Co {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category=category,
        status="active",
        monthly_fee_status="current",
    )
    if tier is not None:
        defaults["tier"] = tier
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
    return profile


def _make_approved_doc(db, partner_org_id, uploader_id):
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        document_type=DocumentType.fiscal_id,
        document_name="fiscal_id.pdf",
        file_path="/tmp/x",
        uploaded_by_user_id=uploader_id,
        status=DocumentStatus.approved,
    )
    db.add(doc)
    db.commit()
    return doc


def _make_user(db, role: UserRole, partner_org_id=None):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@dyn.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _make_config(db, criterion_key, category_code=None, tier_name=None,
                 is_required=True, is_active=True, description=None):
    row = ActivationChecklistConfig(
        id=uuid.uuid4(),
        partner_category_code=category_code,
        tier_name=tier_name,
        criterion_key=criterion_key,
        is_required=is_required,
        is_active=is_active,
        description=description,
    )
    db.add(row)
    db.commit()
    return row


def _fully_activate_partner(db, partner):
    """Helper that sets all four hardcoded flags True for ``partner``."""
    _make_profile(db, partner.id, pct=100)
    uploader = _make_user(db, UserRole.channel_ops_admin)
    _make_approved_doc(db, partner.id, uploader.id)
    partner.contract_start_date = date(2026, 5, 1)
    db.commit()
    # Initial recalc (training still False)
    checklist = recalculate_activation(db, partner.id)
    checklist.baseline_training_complete = True
    db.commit()


# =====================================================================
# Fallback path — no config rows present
# =====================================================================


def test_fallback_no_config_rows_all_flags_false_not_activated(db_session):
    """No ActivationChecklistConfig rows; nothing satisfied → not activated."""
    partner = _make_partner(db_session)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is False
    # resolve_required_criteria should report fallback
    _, source = resolve_required_criteria(db_session, partner)
    assert source == "fallback"


def test_fallback_all_four_flags_true_activates(db_session):
    """No config rows; all four hardcoded flags True → activated."""
    partner = _make_partner(db_session)
    _fully_activate_partner(db_session, partner)
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is True
    assert checklist.documents_uploaded is True
    assert checklist.terms_signed is True
    assert checklist.baseline_training_complete is True
    assert checklist.activation_complete is True


def test_fallback_partial_blocks_activation(db_session):
    """No config rows; missing terms_signed → still not activated."""
    partner = _make_partner(db_session)
    _make_profile(db_session, partner.id, pct=100)
    uploader = _make_user(db_session, UserRole.channel_ops_admin)
    _make_approved_doc(db_session, partner.id, uploader.id)
    checklist = recalculate_activation(db_session, partner.id)
    checklist.baseline_training_complete = True
    db_session.commit()
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.terms_signed is False
    assert checklist.activation_complete is False


# =====================================================================
# Dynamic path — config rows present
# =====================================================================


def test_dynamic_subset_required_only_profile_and_terms(db_session):
    """Only profile_complete and terms_signed required → activates without docs/training."""
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    _make_profile(db_session, partner.id, pct=100)
    _make_config(db_session, "profile_complete")
    _make_config(db_session, "terms_signed")
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.documents_uploaded is False  # not uploaded
    assert checklist.baseline_training_complete is False  # not trained
    assert checklist.activation_complete is True  # only profile + terms required


def test_dynamic_category_match_applies(db_session):
    """Category-scoped row only applies to partners with that category."""
    partner = _make_partner(db_session, category="reseller")
    _make_config(db_session, "profile_complete", category_code="reseller")
    config_rows, source = resolve_required_criteria(db_session, partner)
    assert source == "dynamic"
    keys = [r.criterion_key for r in config_rows]
    assert keys == ["profile_complete"]


def test_dynamic_category_mismatch_falls_back(db_session):
    """Row scoped to a different category → no rows match → fallback."""
    partner = _make_partner(db_session, category="reseller")
    _make_config(db_session, "profile_complete", category_code="master")
    _, source = resolve_required_criteria(db_session, partner)
    assert source == "fallback"


def test_dynamic_tier_match_applies(db_session):
    """Tier-scoped row matches a partner with that tier."""
    partner = _make_partner(db_session, tier="gold")
    _make_config(db_session, "profile_complete", tier_name="gold")
    config_rows, source = resolve_required_criteria(db_session, partner)
    assert source == "dynamic"
    assert [r.criterion_key for r in config_rows] == ["profile_complete"]


def test_dynamic_tier_mismatch_falls_back(db_session):
    """Row scoped to a different tier → fallback."""
    partner = _make_partner(db_session, tier="silver")
    _make_config(db_session, "profile_complete", tier_name="gold")
    _, source = resolve_required_criteria(db_session, partner)
    assert source == "fallback"


def test_dynamic_null_category_applies_to_all(db_session):
    """category_code=NULL row should match a partner of any category."""
    p1 = _make_partner(db_session, category="reseller")
    p2 = _make_partner(db_session, category="master")
    _make_config(db_session, "profile_complete")  # NULL category
    for p in (p1, p2):
        rows, source = resolve_required_criteria(db_session, p)
        assert source == "dynamic"
        assert [r.criterion_key for r in rows] == ["profile_complete"]


def test_dynamic_null_tier_applies_to_all(db_session):
    """tier_name=NULL row should match a partner regardless of tier."""
    p_tiered = _make_partner(db_session, tier="silver")
    p_no_tier = _make_partner(db_session)  # tier left nullable default
    _make_config(db_session, "profile_complete")  # NULL tier
    for p in (p_tiered, p_no_tier):
        rows, source = resolve_required_criteria(db_session, p)
        assert source == "dynamic"
        assert [r.criterion_key for r in rows] == ["profile_complete"]


def test_inactive_or_optional_rows_ignored(db_session):
    """is_active=False or is_required=False rows must not enter the required set."""
    partner = _make_partner(db_session)
    _make_config(db_session, "profile_complete", is_required=False)
    _make_config(db_session, "terms_signed", is_active=False)
    _, source = resolve_required_criteria(db_session, partner)
    assert source == "fallback"  # both rows excluded


def test_partial_dynamic_criteria_not_complete(db_session):
    """4 required criteria, only some met → not activated."""
    partner = _make_partner(db_session)
    _make_profile(db_session, partner.id, pct=100)  # profile complete
    # don't approve docs, no contract date, no training
    _make_config(db_session, "profile_complete")
    _make_config(db_session, "documents_uploaded")
    _make_config(db_session, "terms_signed")
    _make_config(db_session, "baseline_training_complete")
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.profile_complete is True
    assert checklist.documents_uploaded is False
    assert checklist.activation_complete is False


def test_all_dynamic_criteria_met_activates_and_stamps_activated_at(db_session):
    """All four required criteria met dynamically → activated + activated_at set."""
    partner = _make_partner(db_session)
    _fully_activate_partner(db_session, partner)
    _make_config(db_session, "profile_complete")
    _make_config(db_session, "documents_uploaded")
    _make_config(db_session, "terms_signed")
    _make_config(db_session, "baseline_training_complete")
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is True
    assert checklist.activated_at is not None


def test_new_required_row_takes_effect_immediately(db_session):
    """Adding a new required-config row mid-life flips a previously-activated partner."""
    partner = _make_partner(db_session)
    _fully_activate_partner(db_session, partner)
    # Activated with no config rows → fallback path
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is True

    # Admin adds a new required criterion that the partner doesn't satisfy.
    # ``contract_signed`` is aliased to ``terms_signed`` which IS True for
    # this partner. So instead inject an unsatisfied flag.
    partner.contract_start_date = None  # break terms_signed
    db_session.commit()
    _make_config(db_session, "terms_signed")  # explicitly required dynamically
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.terms_signed is False
    assert checklist.activation_complete is False


def test_existing_signature_unchanged_returns_checklist(db_session):
    """Regression guard: recalculate_activation(db, partner_id) → PartnerActivationChecklist."""
    partner = _make_partner(db_session)
    result = recalculate_activation(db_session, partner.id)
    assert isinstance(result, PartnerActivationChecklist)
    assert result.partner_org_id == partner.id


def test_unknown_criterion_key_skipped_gracefully(db_session):
    """Admin adds a criterion not in CRITERION_KEY_MAP → does not block activation."""
    partner = _make_partner(db_session)
    _fully_activate_partner(db_session, partner)
    _make_config(db_session, "payment_setup")  # unknown key, no model field
    checklist = recalculate_activation(db_session, partner.id)
    # All real flags True + unknown key auto-satisfied → activated
    assert checklist.activation_complete is True


def test_contract_signed_alias_maps_to_terms_signed(db_session):
    """``contract_signed`` is an alias for ``terms_signed`` on the same field."""
    partner = _make_partner(db_session, contract_start_date=date(2026, 5, 1))
    _make_config(db_session, "contract_signed")
    checklist = recalculate_activation(db_session, partner.id)
    assert checklist.activation_complete is True


# =====================================================================
# Endpoint tests — GET /partners/{id}/activation/criteria
# =====================================================================


def test_criteria_endpoint_dynamic_source(db_session):
    partner = _make_partner(db_session)
    _fully_activate_partner(db_session, partner)
    _make_config(db_session, "profile_complete")
    _make_config(db_session, "terms_signed")
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["config_source"] == "dynamic"
    keys = sorted(c["criterion_key"] for c in body["required_criteria"])
    assert keys == ["profile_complete", "terms_signed"]
    assert all(c["is_met"] for c in body["required_criteria"])
    assert body["activation_complete"] is True


def test_criteria_endpoint_fallback_source(db_session):
    partner = _make_partner(db_session)
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["config_source"] == "fallback"
    keys = sorted(c["criterion_key"] for c in body["required_criteria"])
    assert keys == sorted(HARDCODED_REQUIRED_KEYS)
    # Fresh partner, nothing satisfied
    assert body["activation_complete"] is False


def test_criteria_endpoint_partner_admin_own_org_ok(db_session):
    partner = _make_partner(db_session)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=partner.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200


def test_criteria_endpoint_partner_admin_other_org_403(db_session):
    p1 = _make_partner(db_session)
    p2 = _make_partner(db_session)
    user = _make_user(db_session, UserRole.partner_admin, partner_org_id=p1.id)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{p2.id}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403


def test_criteria_endpoint_404_unknown_partner(db_session):
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{uuid.uuid4()}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


def test_criteria_endpoint_auto_initialises_checklist(db_session):
    """No checklist row yet → endpoint should still work (initialises via recalc)."""
    partner = _make_partner(db_session)
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activation/criteria")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    checklist = (
        db_session.query(PartnerActivationChecklist)
        .filter_by(partner_org_id=partner.id).first()
    )
    assert checklist is not None
