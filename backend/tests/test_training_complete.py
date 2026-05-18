"""Tests for the baseline_training_complete endpoints (Sprint 9 / FPRM-145).

POST /partners/{id}/activation/training-complete  — sets flag True, recalcs
POST /partners/{id}/activation/training-reset      — sets flag False, recalcs

Permissions: system_admin, channel_ops_admin, channel_manager only.
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
    AuditLog,
    DocumentStatus,
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
        "sqlite:///./test_training_complete.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_training_complete.db"):
        try: os.remove("./test_training_complete.db")
        except OSError: pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try: yield db
    finally: db.close()


def _make_user(role, partner_org_id=None):
    return User(id=uuid.uuid4(), email=f"{role.value}-{uuid.uuid4().hex[:6]}@t.com",
                hashed_password="x", role=role.value, partner_org_id=partner_org_id,
                is_active=True)


def _make_partner_with_three_gates(db):
    """Build a partner that satisfies profile + docs + terms but no training."""
    partner = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Train Co {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category="reseller",
        status="active",
        contract_start_date=date(2026, 5, 1),
    )
    db.add(partner); db.commit(); db.refresh(partner)

    db.add(PartnerProfile(id=uuid.uuid4(), partner_org_id=partner.id,
                          profile_completeness_pct=95))
    uploader = _make_user(UserRole.channel_ops_admin)
    db.add(uploader)
    db.commit()
    for code in ("fiscal_id", "id_legal_representative"):
        db.add(PartnerDocument(
            id=uuid.uuid4(),
            partner_org_id=partner.id,
            document_type=code,
            document_name=f"{code}.pdf",
            file_path="/x",
            uploaded_by_user_id=uploader.id,
            status=DocumentStatus.approved,
        ))
    db.commit()
    return partner


def _override(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


# -------- POST training-complete --------


def test_training_complete_as_system_admin_flips_activation(db_session):
    partner = _make_partner_with_three_gates(db_session)
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()

    client = _override(db_session, admin)
    r = client.post(f"/partners/{partner.id}/activation/training-complete")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["baseline_training_complete"] is True
    assert body["activation_complete"] is True
    assert body["activated_at"] is not None


def test_training_complete_as_channel_manager_ok(db_session):
    partner = _make_partner_with_three_gates(db_session)
    mgr = _make_user(UserRole.channel_manager)
    db_session.add(mgr); db_session.commit()
    client = _override(db_session, mgr)
    r = client.post(f"/partners/{partner.id}/activation/training-complete")
    assert r.status_code == 200
    assert r.json()["baseline_training_complete"] is True


def test_training_complete_as_partner_admin_forbidden(db_session):
    partner = _make_partner_with_three_gates(db_session)
    p = _make_user(UserRole.partner_admin, partner_org_id=partner.id)
    db_session.add(p); db_session.commit()
    client = _override(db_session, p)
    r = client.post(f"/partners/{partner.id}/activation/training-complete")
    assert r.status_code == 403


def test_training_complete_404_unknown_partner(db_session):
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    client = _override(db_session, admin)
    r = client.post(f"/partners/{uuid.uuid4()}/activation/training-complete")
    assert r.status_code == 404


def test_training_complete_creates_checklist_if_missing(db_session):
    partner = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"NoChecklist {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category="reseller",
        status="active",
    )
    db_session.add(partner); db_session.commit()
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    client = _override(db_session, admin)
    r = client.post(f"/partners/{partner.id}/activation/training-complete")
    assert r.status_code == 200
    # checklist now exists with training True, but activation_complete still False
    # because the other three gates aren't met
    assert r.json()["baseline_training_complete"] is True
    assert r.json()["activation_complete"] is False


def test_training_complete_audited(db_session):
    partner = _make_partner_with_three_gates(db_session)
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    client = _override(db_session, admin)
    client.post(f"/partners/{partner.id}/activation/training-complete")

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "partner_activation.training_complete")
        .first()
    )
    assert audit is not None


# -------- POST training-reset --------


def test_training_reset_flips_flag_off(db_session):
    partner = _make_partner_with_three_gates(db_session)
    admin = _make_user(UserRole.system_admin)
    db_session.add(admin); db_session.commit()
    client = _override(db_session, admin)

    # First mark complete
    client.post(f"/partners/{partner.id}/activation/training-complete")
    # Then reset
    r = client.post(f"/partners/{partner.id}/activation/training-reset")
    assert r.status_code == 200
    body = r.json()
    assert body["baseline_training_complete"] is False
    assert body["activation_complete"] is False
    # activated_at preserved even after reset (intentional — was-activated marker)
    assert body["activated_at"] is not None


def test_training_reset_partner_admin_forbidden(db_session):
    partner = _make_partner_with_three_gates(db_session)
    p = _make_user(UserRole.partner_admin, partner_org_id=partner.id)
    db_session.add(p); db_session.commit()
    client = _override(db_session, p)
    r = client.post(f"/partners/{partner.id}/activation/training-reset")
    assert r.status_code == 403
