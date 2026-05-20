"""Tests for FPRM-274 / Sprint 17 — multi-step approval enforcement.

Covers the step-gating logic on POST /applications/{id}/approve and POST
/internal/deals/{id}/approve, the ApprovalStepRecord audit trail, and the
``approval_progress`` block on GET responses for both workflows. Fallback
(single-step legacy) behaviour is asserted explicitly to guard against
regression for existing prod data.
"""
import os
import sys
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user, get_optional_bearer_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    ApplicationStatus,
    ApprovalStepRecord,
    ApprovalWorkflowStep,
    AuditLog,
    DealRegistration,
    PartnerActivationChecklist,
    PartnerApplication,
    PartnerOrganization,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_approval_enforcement.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_approval_enforcement.db"):
        try:
            os.remove("./test_approval_enforcement.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        # Each test starts from a clean approval-workflow state so cases
        # can opt into "no steps" or build their own step set.
        db.query(ApprovalStepRecord).delete()
        db.query(ApprovalWorkflowStep).delete()
        db.commit()
        yield db
    finally:
        db.query(ApprovalStepRecord).delete()
        db.query(ApprovalWorkflowStep).delete()
        db.commit()
        db.close()


def _override(db_session, user=None):
    """Override the DB and (optionally) BOTH auth dependencies.

    GET /applications/{id} uses ``get_optional_bearer_user`` (dual-auth via
    draft_token OR JWT) while approve/reject use ``get_current_user`` (and
    its ``require_permission`` wrapper). Tests override both so the same
    user surfaces regardless of which endpoint is being exercised.
    """
    def _db_dep():
        yield db_session
    app.dependency_overrides[get_db] = _db_dep
    if user is not None:
        def _user_dep():
            return user
        app.dependency_overrides[get_current_user] = _user_dep
        app.dependency_overrides[get_optional_bearer_user] = _user_dep


def _make_user(db, role: UserRole, partner_org_id=None):
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@apr.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _make_step(db, workflow_type, step_order, step_name, required_role,
               is_active=True):
    step = ApprovalWorkflowStep(
        id=uuid.uuid4(),
        workflow_type=workflow_type,
        step_order=step_order,
        step_name=step_name,
        required_role=required_role,
        is_active=is_active,
    )
    db.add(step)
    db.commit()
    return step


def _make_application(db, status=ApplicationStatus.submitted):
    """Create a minimally-valid PartnerApplication in the requested status."""
    appl = PartnerApplication(
        id=uuid.uuid4(),
        status=status,
        applicant_email=f"a-{uuid.uuid4().hex[:6]}@x.test",
        applicant_name="Applicant",
        legal_name="Acme Co",
        terms_accepted=True,
        terms_accepted_at=datetime.utcnow(),
        submitted_at=datetime.utcnow(),
    )
    db.add(appl)
    db.commit()
    return appl


def _make_partner_for_deals(db):
    """Create a partner org with an active checklist so deal endpoints work."""
    partner = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Partner {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category="reseller",
        status="active",
        monthly_fee_status="current",
        contract_start_date=date(2026, 5, 1),
    )
    db.add(partner)
    checklist = PartnerActivationChecklist(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        profile_complete=True,
        documents_uploaded=True,
        terms_signed=True,
        baseline_training_complete=True,
        activation_complete=True,
        activated_at=datetime.utcnow(),
    )
    db.add(checklist)
    db.commit()
    return partner


def _make_deal_under_review(db, partner):
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        status="under_review",
        customer_name="Customer LLC",
        deal_name="Sample Deal",
        submitted_at=datetime.utcnow(),
    )
    db.add(deal)
    db.commit()
    return deal


# ======================================================================
# Fallback (no steps configured) — legacy single-approval behaviour
# ======================================================================


def test_no_steps_configured_application_approve_succeeds(db_session):
    """No workflow steps; any review-role user can approve directly to approved."""
    appl = _make_application(db_session)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"


def test_no_steps_any_review_role_can_approve(db_session):
    """Fallback path: channel_manager (not channel_ops_admin) still approves OK."""
    appl = _make_application(db_session)
    reviewer = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200


def test_get_application_no_steps_approval_progress_null(db_session):
    """No steps configured → GET returns approval_progress=None."""
    appl = _make_application(db_session)
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.get(f"/applications/{appl.id}")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["approval_progress"] is None


def test_get_deal_no_steps_approval_progress_null(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    reviewer = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.get(f"/deal-registrations/{deal.id}")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["approval_progress"] is None


# ======================================================================
# Step-gated application approval
# ======================================================================


def test_single_step_correct_role_approves(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Channel Ops Review", "channel_ops_admin")
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    rec = db_session.query(ApprovalStepRecord).filter_by(object_id=appl.id).one()
    assert rec.step_order == 1
    assert rec.action == "approved"


def test_single_step_wrong_role_403(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Channel Ops Review", "channel_ops_admin")
    reviewer = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert "channel_ops_admin" in r.json()["detail"]


def test_two_step_first_approval_stays_pending(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Ops Check", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Manager Approval", "channel_manager")
    reviewer = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve", json={"notes": "ok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    body = r.json()
    # Status MUST NOT flip on intermediate step
    db_session.refresh(appl)
    assert appl.status in (ApplicationStatus.submitted, ApplicationStatus.under_review)
    progress = body["approval_progress"]
    assert progress["total_steps"] == 2
    assert progress["completed_steps"] == 1
    assert progress["current_step_order"] == 2
    assert progress["current_required_role"] == "channel_manager"


def test_two_step_second_approval_completes(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Ops Check", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Manager Approval", "channel_manager")
    ops = _make_user(db_session, UserRole.channel_ops_admin)
    mgr = _make_user(db_session, UserRole.channel_manager)
    # Step 1
    _override(db_session, ops)
    try:
        client = TestClient(app)
        client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    # Step 2
    _override(db_session, mgr)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    db_session.refresh(appl)
    assert appl.status == ApplicationStatus.approved


def test_cannot_skip_step(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Ops Check", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Manager Approval", "channel_manager")
    # channel_manager tries to approve before step 1 is done
    mgr = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, mgr)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert "channel_ops_admin" in r.json()["detail"]


def test_reject_records_step_and_terminates(db_session):
    appl = _make_application(db_session, status=ApplicationStatus.under_review)
    _make_step(db_session, "partner_application", 1, "Ops Check", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Manager Approval", "channel_manager")
    ops = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, ops)
    try:
        client = TestClient(app)
        r = client.post(f"/applications/{appl.id}/reject", json={"rejection_reason": "spam"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    rec = db_session.query(ApprovalStepRecord).filter_by(object_id=appl.id).one()
    assert rec.action == "rejected"
    assert rec.step_order == 1


def test_get_application_returns_progress_block(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Ops", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Mgr", "channel_manager")
    reviewer = _make_user(db_session, UserRole.system_admin)
    _override(db_session, reviewer)
    try:
        client = TestClient(app)
        r = client.get(f"/applications/{appl.id}")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    progress = r.json()["approval_progress"]
    assert progress["total_steps"] == 2
    assert progress["completed_steps"] == 0
    assert progress["current_required_role"] == "channel_ops_admin"


def test_audit_log_step_approved_then_approved(db_session):
    appl = _make_application(db_session)
    _make_step(db_session, "partner_application", 1, "Ops", "channel_ops_admin")
    _make_step(db_session, "partner_application", 2, "Mgr", "channel_manager")
    ops = _make_user(db_session, UserRole.channel_ops_admin)
    mgr = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, ops)
    try:
        TestClient(app).post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()
    _override(db_session, mgr)
    try:
        TestClient(app).post(f"/applications/{appl.id}/approve")
    finally:
        app.dependency_overrides.clear()

    actions = [
        row.action
        for row in db_session.query(AuditLog)
        .filter_by(object_id=appl.id)
        .order_by(AuditLog.timestamp)
        .all()
    ]
    assert "partner_application.step_approved" in actions
    assert "partner_application.approved" in actions
    # step_approved must come before approved
    assert actions.index("partner_application.step_approved") < actions.index("partner_application.approved")


# ======================================================================
# Deal-registration approval — same pattern
# ======================================================================


def test_deal_single_step_correct_role_approves(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr Approval", "channel_manager")
    mgr = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, mgr)
    try:
        client = TestClient(app)
        r = client.post(f"/internal/deals/{deal.id}/approve",
                        json={"review_notes": "looks good"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    db_session.refresh(deal)
    assert deal.status == "approved"
    rec = db_session.query(ApprovalStepRecord).filter_by(object_id=deal.id).one()
    assert rec.action == "approved"


def test_deal_wrong_role_403(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr Approval", "channel_manager")
    other = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, other)
    try:
        client = TestClient(app)
        r = client.post(f"/internal/deals/{deal.id}/approve",
                        json={"review_notes": "ok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert "channel_manager" in r.json()["detail"]


def test_deal_two_step_intermediate_stays_under_review(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr", "channel_manager")
    _make_step(db_session, "deal_registration", 2, "Ops", "channel_ops_admin")
    mgr = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, mgr)
    try:
        client = TestClient(app)
        r = client.post(f"/internal/deals/{deal.id}/approve",
                        json={"review_notes": "step 1 ok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    db_session.refresh(deal)
    assert deal.status == "under_review"
    progress = r.json()["approval_progress"]
    assert progress["completed_steps"] == 1
    assert progress["current_required_role"] == "channel_ops_admin"


def test_deal_two_step_final_step_approves(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr", "channel_manager")
    _make_step(db_session, "deal_registration", 2, "Ops", "channel_ops_admin")
    mgr = _make_user(db_session, UserRole.channel_manager)
    ops = _make_user(db_session, UserRole.channel_ops_admin)
    _override(db_session, mgr)
    try:
        TestClient(app).post(f"/internal/deals/{deal.id}/approve",
                             json={"review_notes": "ok"})
    finally:
        app.dependency_overrides.clear()
    _override(db_session, ops)
    try:
        r = TestClient(app).post(f"/internal/deals/{deal.id}/approve",
                                 json={"review_notes": "final ok"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    db_session.refresh(deal)
    assert deal.status == "approved"


def test_deal_reject_creates_step_record(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr", "channel_manager")
    mgr = _make_user(db_session, UserRole.channel_manager)
    _override(db_session, mgr)
    try:
        client = TestClient(app)
        r = client.post(f"/internal/deals/{deal.id}/reject",
                        json={"review_notes": "duplicate"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    rec = db_session.query(ApprovalStepRecord).filter_by(object_id=deal.id).one()
    assert rec.action == "rejected"


def test_get_deal_returns_progress_block(db_session):
    partner = _make_partner_for_deals(db_session)
    deal = _make_deal_under_review(db_session, partner)
    _make_step(db_session, "deal_registration", 1, "Mgr", "channel_manager")
    _make_step(db_session, "deal_registration", 2, "Ops", "channel_ops_admin")
    user = _make_user(db_session, UserRole.system_admin)
    _override(db_session, user)
    try:
        r = TestClient(app).get(f"/deal-registrations/{deal.id}")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    progress = r.json()["approval_progress"]
    assert progress["total_steps"] == 2
    assert progress["current_step_order"] == 1
