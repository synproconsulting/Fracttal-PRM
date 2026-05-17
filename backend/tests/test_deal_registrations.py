"""Tests for the deal_registrations router (Sprint 8 / FPRM-128)."""
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal

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
    CommissionStructure,
    CommissionType,
    CommissionYear,
    DealRegistration,
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerCategoryConfig,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_deal_registrations.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_deal_registrations.db"):
        try:
            os.remove("./test_deal_registrations.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def make_user(role: UserRole, partner_org_id=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def make_org(db) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Deal Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def make_checklist(db, org_id, *, complete: bool) -> PartnerActivationChecklist:
    checklist = PartnerActivationChecklist(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        profile_complete=complete,
        documents_uploaded=complete,
        terms_signed=complete,
        activation_complete=complete,
    )
    db.add(checklist)
    db.commit()
    return checklist


def make_deal(db, org_id, *, status="draft", customer="ACME", name="Deal X") -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        status=status,
        customer_name=customer,
        deal_name=name,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def seed_commission_struct(db) -> None:
    """Seed one category + one commission row that matches the test scenario."""
    cat = PartnerCategoryConfig(
        id=uuid.uuid4(),
        code="reseller",
        display_name="Reseller",
        deal_reg_sla_hours=96,
        max_discount_pct=Decimal("20"),
    )
    db.add(cat)
    db.commit()
    row = CommissionStructure(
        id=uuid.uuid4(),
        partner_category_code="reseller",
        commission_type=CommissionType.autonomous_sell,
        year=CommissionYear.year_1,
        commission_pct=Decimal("50.0"),
    )
    db.add(row)
    db.commit()


def override_user(db_session, user):
    def _override_db():
        yield db_session

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user


def clear_overrides():
    app.dependency_overrides.clear()


# ------------------ POST /deal-registrations ------------------


def test_create_draft_returns_201_and_persists(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Globex",
            "deal_name": "Globex — CMMS",
            "customer_domain": "globex.com",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "draft"
        assert body["customer_name"] == "Globex"
        assert body["deal_name"] == "Globex — CMMS"
        assert body["partner_org_id"] == str(org.id)
        assert body["conflict_status"] == "not_checked"
    finally:
        clear_overrides()


def test_activation_gate_blocks_create_when_incomplete(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=False)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Blocked Co",
            "deal_name": "Blocked Deal",
        })
        assert r.status_code == 412
        body = r.json()
        # FastAPI nests dict detail into `detail`
        assert body["detail"]["detail"] == "Partner activation incomplete"
        assert body["detail"]["activation_url"] == "/portal/home"
    finally:
        clear_overrides()


def test_activation_gate_blocks_create_when_no_checklist(db_session):
    org = make_org(db_session)
    # No checklist row at all
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "No Checklist Co",
            "deal_name": "No Checklist Deal",
        })
        assert r.status_code == 412
    finally:
        clear_overrides()


def test_create_rejects_partner_user_role(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_user, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "A", "deal_name": "B",
        })
        assert r.status_code == 403
    finally:
        clear_overrides()


def test_create_requires_customer_name_and_deal_name(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={"deal_name": "Only deal"})
        assert r.status_code == 422
        r2 = client.post("/deal-registrations", json={"customer_name": "Only cust"})
        assert r2.status_code == 422
    finally:
        clear_overrides()


# ------------------ GET /deal-registrations ------------------


def test_list_deals_partner_admin_only_own_org(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    make_checklist(db_session, org_a.id, complete=True)
    make_deal(db_session, org_a.id, name="A-deal")
    make_deal(db_session, org_b.id, name="B-deal")
    user = make_user(UserRole.partner_admin, partner_org_id=org_a.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/deal-registrations")
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(it["partner_org_id"] == str(org_a.id) for it in items)
        names = [it["deal_name"] for it in items]
        assert "A-deal" in names
        assert "B-deal" not in names
    finally:
        clear_overrides()


def test_list_deals_internal_sees_all_and_can_filter(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    make_deal(db_session, org_a.id, name="A-int")
    make_deal(db_session, org_b.id, name="B-int")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/deal-registrations")
        assert r.status_code == 200
        assert r.json()["total"] >= 2
        r2 = client.get(f"/deal-registrations?partner_org_id={org_a.id}")
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert all(it["partner_org_id"] == str(org_a.id) for it in items)
    finally:
        clear_overrides()


# ------------------ GET /deal-registrations/{id} ------------------


def test_get_deal_partner_admin_blocked_on_other_org(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    deal_b = make_deal(db_session, org_b.id)
    user = make_user(UserRole.partner_admin, partner_org_id=org_a.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get(f"/deal-registrations/{deal_b.id}")
        assert r.status_code == 403
    finally:
        clear_overrides()


def test_get_deal_channel_manager_sees_any(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get(f"/deal-registrations/{deal.id}")
        assert r.status_code == 200
        assert r.json()["id"] == str(deal.id)
    finally:
        clear_overrides()


# ------------------ PATCH /deal-registrations/{id} ------------------


def test_patch_draft_updates_fields(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    deal = make_deal(db_session, org.id)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Updated Co",
            "deal_notes": "Hot lead",
            "status": "approved",  # should NOT be writable via PATCH
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["customer_name"] == "Updated Co"
        assert body["deal_notes"] == "Hot lead"
        assert body["status"] == "draft"
    finally:
        clear_overrides()


def test_patch_submitted_deal_returns_400(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="submitted")
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={"customer_name": "X"})
        assert r.status_code == 400
    finally:
        clear_overrides()


# ------------------ POST /deal-registrations/{id}/submit ------------------


def test_submit_transitions_status_and_logs_audit(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/deal-registrations/{deal.id}/submit")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "submitted"
        assert body["submitted_at"] is not None

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.object_id == deal.id, AuditLog.action == "deal_registration.submitted")
            .first()
        )
        assert entry is not None
    finally:
        clear_overrides()


def test_submit_snapshots_commission_when_row_matches(db_session):
    seed_commission_struct(db_session)
    org = make_org(db_session)  # category=reseller
    deal = make_deal(db_session, org.id)
    deal.commission_type = CommissionType.autonomous_sell.value
    db_session.commit()
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/deal-registrations/{deal.id}/submit")
        assert r.status_code == 200
        body = r.json()
        assert body["commission_structure_id"] is not None
        assert body["commission_rate_snapshot"] == pytest.approx(50.0)
    finally:
        clear_overrides()


def test_submit_no_matching_commission_row_leaves_snapshot_null(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    deal.commission_type = "reseller"  # not a value in CommissionType enum
    db_session.commit()
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/deal-registrations/{deal.id}/submit")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "submitted"
        assert body["commission_structure_id"] is None
        assert body["commission_rate_snapshot"] is None
    finally:
        clear_overrides()


def test_submit_blocked_when_already_submitted(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="under_review")
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/deal-registrations/{deal.id}/submit")
        assert r.status_code == 400
    finally:
        clear_overrides()


# ------------------ DELETE /deal-registrations/{id} ------------------


def test_delete_draft_returns_204(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.delete(f"/deal-registrations/{deal.id}")
        assert r.status_code == 204
        gone = db_session.query(DealRegistration).filter(DealRegistration.id == deal.id).first()
        assert gone is None
    finally:
        clear_overrides()


def test_delete_submitted_deal_returns_400(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="submitted")
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.delete(f"/deal-registrations/{deal.id}")
        assert r.status_code == 400
    finally:
        clear_overrides()


def test_delete_other_orgs_deal_returns_403(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    deal = make_deal(db_session, org_b.id)
    user = make_user(UserRole.partner_admin, partner_org_id=org_a.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.delete(f"/deal-registrations/{deal.id}")
        assert r.status_code == 403
    finally:
        clear_overrides()


# ------------------ Internal deal review endpoints (Story 5 / FPRM-134) ------------------


def test_internal_list_returns_all_deals_for_review_role(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    make_deal(db_session, org_a.id, status="submitted", name="QueueA")
    make_deal(db_session, org_b.id, status="under_review", name="QueueB")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals")
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        names = [it["deal_name"] for it in items]
        assert "QueueA" in names and "QueueB" in names
    finally:
        clear_overrides()


def test_internal_list_supports_status_and_partner_filters(db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    make_deal(db_session, org_a.id, status="submitted", name="FilterA")
    make_deal(db_session, org_b.id, status="approved", name="FilterB")
    user = make_user(UserRole.system_admin)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?status=submitted")
        assert r.status_code == 200
        names = [it["deal_name"] for it in r.json()["items"]]
        assert "FilterA" in names and "FilterB" not in names

        r2 = client.get(f"/internal/deals?partner_org_id={org_a.id}")
        items = r2.json()["items"]
        assert all(it["partner_org_id"] == str(org_a.id) for it in items)
    finally:
        clear_overrides()


def test_internal_list_rejects_partner_admin(db_session):
    org = make_org(db_session)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals")
        assert r.status_code == 403
    finally:
        clear_overrides()


def test_start_review_transitions_submitted_to_under_review(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="submitted")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/internal/deals/{deal.id}/start-review")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "under_review"
        assert body["reviewer_id"] == str(user.id)
    finally:
        clear_overrides()


def test_start_review_rejects_non_submitted_status(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="draft")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/internal/deals/{deal.id}/start-review")
        assert r.status_code == 400
    finally:
        clear_overrides()


def test_approve_requires_review_notes_and_transitions(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="under_review")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r_missing = client.post(f"/internal/deals/{deal.id}/approve", json={})
        assert r_missing.status_code == 422

        r = client.post(f"/internal/deals/{deal.id}/approve", json={"review_notes": "Looks good"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "approved"
        assert body["review_notes"] == "Looks good"
        assert body["reviewer_id"] == str(user.id)

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.object_id == deal.id, AuditLog.action == "deal_registration.approved")
            .first()
        )
        assert entry is not None
    finally:
        clear_overrides()


def test_reject_requires_review_notes_and_transitions(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="under_review")
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r_missing = client.post(f"/internal/deals/{deal.id}/reject", json={"review_notes": ""})
        assert r_missing.status_code == 422

        r = client.post(f"/internal/deals/{deal.id}/reject", json={"review_notes": "Conflicting deal"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "rejected"
        assert body["review_notes"] == "Conflicting deal"

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.object_id == deal.id, AuditLog.action == "deal_registration.rejected")
            .first()
        )
        assert entry is not None
    finally:
        clear_overrides()


def test_approve_partner_admin_blocked(db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id, status="under_review")
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post(f"/internal/deals/{deal.id}/approve", json={"review_notes": "OK"})
        assert r.status_code == 403
    finally:
        clear_overrides()
