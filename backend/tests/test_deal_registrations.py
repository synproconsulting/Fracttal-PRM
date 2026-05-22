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


def test_internal_list_default_sort_is_submitted_desc_then_created_desc(db_session):
    """No ?sort_by= => submitted deals first (newest submission), drafts last.

    PR #139 changed this default to a single-column created_at DESC, which let
    drafts (no submitted_at, but later created_at) float to the top of the
    internal review queue. Restored to the composite the CSV export already
    used.
    """
    from datetime import datetime, timedelta
    org = make_org(db_session)
    now = datetime.utcnow()
    # Order of creation interleaves drafts and submitted deals on purpose so
    # a single-column created_at sort would yield a different ordering.
    d_draft_old = make_deal(db_session, org.id, status="draft", name="DraftOld")
    d_submitted_old = make_deal(db_session, org.id, status="submitted", name="SubmittedOld")
    d_submitted_old.submitted_at = now - timedelta(days=5)
    d_submitted_old.created_at = now - timedelta(days=10)  # created earliest
    d_draft_new = make_deal(db_session, org.id, status="draft", name="DraftNew")
    d_draft_new.created_at = now  # newest created
    d_submitted_new = make_deal(db_session, org.id, status="submitted", name="SubmittedNew")
    d_submitted_new.submitted_at = now - timedelta(days=1)  # newest submission
    d_submitted_new.created_at = now - timedelta(days=2)
    # And pin draft_old created_at between the two submitted rows
    d_draft_old.created_at = now - timedelta(days=3)
    db_session.commit()

    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        # Scope to this test's org so earlier tests' deals (shared sqlite file)
        # don't pollute the result set.
        r = client.get(f"/internal/deals?partner_org_id={org.id}")
        assert r.status_code == 200, r.text
        names = [it["deal_name"] for it in r.json()["items"]]
        # Expected order: submitted (newest first) THEN drafts by created_at desc
        assert names == ["SubmittedNew", "SubmittedOld", "DraftNew", "DraftOld"], names
    finally:
        clear_overrides()


def test_internal_list_explicit_sort_by_overrides_default(db_session):
    """When ?sort_by= IS provided, the single-column apply_sort path runs.

    This is the PR #139 behaviour and must not regress.
    """
    from datetime import datetime, timedelta
    org = make_org(db_session)
    now = datetime.utcnow()
    d_a = make_deal(db_session, org.id, status="submitted", name="Apple")
    d_b = make_deal(db_session, org.id, status="submitted", name="Banana")
    d_c = make_deal(db_session, org.id, status="draft", name="Cherry")
    d_a.submitted_at = now - timedelta(days=1)
    d_b.submitted_at = now - timedelta(days=2)
    db_session.commit()

    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        # Explicit deal_name ASC -- ignores submitted_at composite entirely.
        # Scope to this test's org so earlier tests' deals don't pollute.
        r = client.get(f"/internal/deals?partner_org_id={org.id}&sort_by=deal_name&sort_dir=asc")
        assert r.status_code == 200
        names = [it["deal_name"] for it in r.json()["items"]]
        assert names == ["Apple", "Banana", "Cherry"], names
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


# ------------------ Sprint 20 / FPRM-316 -- Section A + B SPICED API ------------------


def test_create_deal_with_full_section_a_persists(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "SectionA Co",
            "deal_name": "Section A Deal",
            "engagement_date": "2026-05-20",
            "prospect_phone": "+27 11 555 0123",
            "compiled_by": "ops@partner.example",
            "prospect_contact_name": "Alex Smith",
            "prospect_contact_position": "Maintenance Manager",
            "prospect_website": "https://example.com",
            "industry_sector": "Manufacturing",
            "company_size": "51-200",
            "feature_plan_preference": "professional",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["engagement_date"] == "2026-05-20"
        assert body["prospect_phone"] == "+27 11 555 0123"
        assert body["compiled_by"] == "ops@partner.example"
        assert body["prospect_contact_name"] == "Alex Smith"
        assert body["prospect_contact_position"] == "Maintenance Manager"
        assert body["prospect_website"] == "https://example.com"
        assert body["industry_sector"] == "Manufacturing"
        assert body["company_size"] == "51-200"
        assert body["feature_plan_preference"] == "professional"
    finally:
        clear_overrides()


def test_patch_deal_updates_section_b_fields(db_session):
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            # Current systems
            "current_system": "excel",
            "monitoring_system": "none",
            # Features (some True, some False, some left null)
            "need_asset_depreciation": True,
            "need_integration": True,
            "integration_with": "SAP, Power BI",
            "need_multi_language": True,
            "languages_required": "English, Spanish",
            "need_purchasing": False,
            # SPICED
            "about_client": "Mid-size manufacturer with 3 plants.",
            "pain": "Manual coordination across plants.",
            "critical_event": "Existing CMMS licence renewal 2026-09-30.",
            "next_steps": "Demo next week.",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["current_system"] == "excel"
        assert body["monitoring_system"] == "none"
        assert body["need_asset_depreciation"] is True
        assert body["need_integration"] is True
        assert body["integration_with"] == "SAP, Power BI"
        assert body["need_multi_language"] is True
        assert body["languages_required"] == "English, Spanish"
        assert body["need_purchasing"] is False
        assert body["about_client"].startswith("Mid-size")
        assert "renewal 2026-09-30" in body["critical_event"]
        assert body["next_steps"] == "Demo next week."
    finally:
        clear_overrides()


def test_create_deal_without_section_b_no_regression(db_session):
    """Partners submitting deals without any new Section A/B fields must still
    succeed -- enforces the no-regression promise from Story 1.
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Bare Co",
            "deal_name": "Bare Deal",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        # All new Section A/B fields are null on a bare create
        for k in (
            "engagement_date", "prospect_phone", "compiled_by",
            "prospect_contact_name", "company_size", "feature_plan_preference",
            "current_system", "monitoring_system",
            "need_asset_depreciation", "need_integration", "integration_with",
            "about_client", "pain", "next_steps",
        ):
            assert body[k] is None, f"expected null on bare create: {k} = {body[k]!r}"
        # created_on_behalf_of is NOT NULL with server default False
        assert body["created_on_behalf_of"] is False
    finally:
        clear_overrides()


def test_feature_plan_preference_returned_on_get(db_session):
    """GET /deal-registrations/{id} must surface feature_plan_preference so
    the QuoteForm can pre-populate the plan dropdown (Phase 6 deal -> quote
    handoff).
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)
    deal.feature_plan_preference = "enterprise"
    db_session.commit()
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get(f"/deal-registrations/{deal.id}")
        assert r.status_code == 200
        assert r.json()["feature_plan_preference"] == "enterprise"
    finally:
        clear_overrides()


def test_section_b_booleans_round_trip_true_false_null(db_session):
    """The 13 need_* booleans accept True, False, and None distinctly --
    matches the form's three-state checkbox (checked / explicitly-no / unset).
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "need_reports": True,
            "need_tool_management": False,
            # need_purchasing left unset -> remains null
            "need_track_labour": True,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["need_reports"] is True
        assert body["need_tool_management"] is False
        assert body["need_purchasing"] is None
        assert body["need_track_labour"] is True
    finally:
        clear_overrides()


def test_customer_contact_position_round_trips_via_post_and_patch(db_session):
    """Regression for the PR #134 oversight -- the form's customer-side
    "Contact title" was being silently dropped because the column was
    missing, the whitelist entry was missing, and the model lacked the
    field. Migration 030 + the CREATABLE_FIELDS update + the model column
    close that gap. This test would have caught the bug at PR time."""
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Title Co",
            "deal_name": "Title Deal",
            "customer_contact_position": "VP Operations",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        deal_id = body["id"]
        assert body["customer_contact_position"] == "VP Operations"

        # PATCH updates the field
        r = client.patch(f"/deal-registrations/{deal_id}", json={
            "customer_contact_position": "Director of Maintenance",
        })
        assert r.status_code == 200
        assert r.json()["customer_contact_position"] == "Director of Maintenance"

        # GET reads it back
        r = client.get(f"/deal-registrations/{deal_id}")
        assert r.status_code == 200
        assert r.json()["customer_contact_position"] == "Director of Maintenance"

        # Bare create leaves it null -- no regression for legacy payloads
        r = client.post("/deal-registrations", json={
            "customer_name": "Bare Title Co",
            "deal_name": "Bare Title Deal",
        })
        assert r.status_code == 201
        assert r.json()["customer_contact_position"] is None
    finally:
        clear_overrides()


def test_license_qty_fields_round_trip(db_session):
    """Post-Sprint 20 deal form fix -- partners capture requested license
    counts on the deal (migration 029). Both columns are nullable so legacy
    deals stay valid; null payload values come back as null.
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        # Create with explicit license counts
        r = client.post("/deal-registrations", json={
            "customer_name": "License Co",
            "deal_name": "License Deal",
            "qty_transactional_users": 25,
            "qty_limited_tech_users": 10,
        })
        assert r.status_code == 201, r.text
        body = r.json()
        deal_id = body["id"]
        assert body["qty_transactional_users"] == 25
        assert body["qty_limited_tech_users"] == 10

        # PATCH can update both fields independently
        r = client.patch(f"/deal-registrations/{deal_id}", json={
            "qty_transactional_users": 30,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["qty_transactional_users"] == 30
        assert body["qty_limited_tech_users"] == 10

        # Bare create (no qty fields) leaves both null -- no regression
        r = client.post("/deal-registrations", json={
            "customer_name": "Bare License Co",
            "deal_name": "Bare License Deal",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["qty_transactional_users"] is None
        assert body["qty_limited_tech_users"] is None
    finally:
        clear_overrides()


def test_created_on_behalf_of_not_settable_via_partner_patch(db_session):
    """FPRM-317 lockdown -- the partner-facing PATCH whitelist must NOT allow
    a partner to flip created_on_behalf_of. That column is set server-side by
    the internal-create path only.
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)  # default False
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "created_on_behalf_of": True,
            "about_client": "Sneaky attempt.",  # also a real edit, so the
            # PATCH does change something legitimate
        })
        assert r.status_code == 200
        body = r.json()
        # the legitimate field was applied
        assert body["about_client"] == "Sneaky attempt."
        # but created_on_behalf_of stayed False (whitelist rejected the override)
        assert body["created_on_behalf_of"] is False
    finally:
        clear_overrides()


# ------------------ Sprint 20 / FPRM-317 -- Internal deal creation ------------------


def test_channel_manager_can_create_deal_on_behalf_of_partner(db_session):
    org = make_org(db_session)
    # Note: NO activation checklist -- channel manager skips that gate.
    user = make_user(UserRole.channel_manager)  # no partner_org_id (internal)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "partner_org_id": str(org.id),
            "customer_name": "Behalf Customer",
            "deal_name": "Behalf Deal",
            "about_client": "Captured during initial intro call.",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["partner_org_id"] == str(org.id)
        assert body["status"] == "draft"
        assert body["created_on_behalf_of"] is True
        assert body["about_client"].startswith("Captured")
    finally:
        clear_overrides()


def test_internal_create_without_partner_org_id_returns_422(db_session):
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Anon Customer",
            "deal_name": "Anon Deal",
        })
        assert r.status_code == 422
        assert "partner_org_id" in r.json()["detail"]
    finally:
        clear_overrides()


def test_internal_create_with_nonexistent_partner_org_returns_404(db_session):
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "partner_org_id": str(uuid.uuid4()),
            "customer_name": "Ghost Customer",
            "deal_name": "Ghost Deal",
        })
        assert r.status_code == 404
    finally:
        clear_overrides()


def test_internal_create_with_inactive_partner_returns_422(db_session):
    from models import PartnerStatus as _PS
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Suspended Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=_PS.suspended,
    )
    db_session.add(org)
    db_session.commit()
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "partner_org_id": str(org.id),
            "customer_name": "Suspended Customer",
            "deal_name": "Suspended Deal",
        })
        assert r.status_code == 422
        assert "not active" in r.json()["detail"]
    finally:
        clear_overrides()


def test_partner_admin_post_still_works_no_regression(db_session):
    """Regression guard for FPRM-317: the existing partner-side POST must
    continue to honour the activation gate and never need partner_org_id.
    """
    org = make_org(db_session)
    make_checklist(db_session, org.id, complete=True)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "customer_name": "Regression Customer",
            "deal_name": "Regression Deal",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["partner_org_id"] == str(org.id)
        assert body["created_on_behalf_of"] is False  # partner-created
    finally:
        clear_overrides()


def test_internal_create_logs_distinct_audit_event(db_session):
    org = make_org(db_session)
    user = make_user(UserRole.channel_manager)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "partner_org_id": str(org.id),
            "customer_name": "Audited Customer",
            "deal_name": "Audited Deal",
        })
        assert r.status_code == 201
        deal_id = uuid.UUID(r.json()["id"])
        entry = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.object_id == deal_id,
                AuditLog.action == "deal_registration.created_internal",
            )
            .first()
        )
        assert entry is not None
        assert "partner_org_id" in entry.after_state
    finally:
        clear_overrides()


def test_partner_user_role_cannot_create_on_behalf(db_session):
    """partner_user is neither partner_admin nor internal -- 403 either way."""
    org = make_org(db_session)
    user = make_user(UserRole.partner_user, partner_org_id=org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.post("/deal-registrations", json={
            "partner_org_id": str(org.id),
            "customer_name": "Blocked Customer",
            "deal_name": "Blocked Deal",
        })
        assert r.status_code == 403
    finally:
        clear_overrides()


# ------------------ Post-Sprint 20 PR B: internal admin editability ------------------


def _count_field_events(db, deal_id):
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.object_type == "deal_registration",
            AuditLog.object_id == deal_id,
            AuditLog.action == "deal.field_updated",
        )
        .count()
    )


def test_system_admin_can_patch_deal_in_any_status(db_session):
    """system_admin can edit a deal even after submission / approval --
    internal admins need to correct typos at any stage."""
    org = make_org(db_session)
    admin = make_user(UserRole.system_admin)
    for status in ("draft", "submitted", "under_review", "approved", "rejected"):
        deal = make_deal(db_session, org.id, status=status, name=f"Deal {status}")
        override_user(db_session, admin)
        client = TestClient(app)
        try:
            r = client.patch(f"/deal-registrations/{deal.id}", json={
                "customer_name": f"Corrected {status}",
                "about_client": "Post-submission correction.",
            })
            assert r.status_code == 200, f"status={status}: {r.text}"
            body = r.json()
            assert body["customer_name"] == f"Corrected {status}"
            assert body["about_client"] == "Post-submission correction."
            # Status must not change as a side-effect of the edit.
            assert body["status"] == status
        finally:
            clear_overrides()


def test_channel_ops_admin_can_patch_deal_in_any_status(db_session):
    """channel_ops_admin has the same edit reach as system_admin."""
    org = make_org(db_session)
    admin = make_user(UserRole.channel_ops_admin)
    deal = make_deal(db_session, org.id, status="approved", name="Approved Deal")
    override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "deal_name": "Approved Deal (renamed)",
        })
        assert r.status_code == 200, r.text
        assert r.json()["deal_name"] == "Approved Deal (renamed)"
    finally:
        clear_overrides()


def test_channel_manager_cannot_patch_deal_fields(db_session):
    """Channel managers retain only review actions; they cannot edit deal
    fields directly. They fall through to the partner_admin gate and
    fail it because they aren't a partner_admin."""
    org = make_org(db_session)
    mgr = make_user(UserRole.channel_manager)
    deal = make_deal(db_session, org.id, status="under_review")
    override_user(db_session, mgr)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Tampered",
        })
        assert r.status_code == 403
    finally:
        clear_overrides()


def test_internal_admin_patch_logs_field_updated_audit_per_change(db_session):
    """Every changed whitelisted field must produce a deal.field_updated
    event with the right before/after values. Unchanged fields must not
    produce an event."""
    org = make_org(db_session)
    admin = make_user(UserRole.system_admin)
    deal = make_deal(db_session, org.id, status="approved", customer="Old Co", name="Old Deal")
    deal.customer_contact_email = "old@example.com"
    db_session.commit()
    db_session.refresh(deal)
    before_count = _count_field_events(db_session, deal.id)

    override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "New Co",
            "customer_contact_email": "new@example.com",
            # no-op: same as current
            "deal_name": "Old Deal",
        })
        assert r.status_code == 200, r.text
    finally:
        clear_overrides()

    events = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.object_type == "deal_registration",
            AuditLog.object_id == deal.id,
            AuditLog.action == "deal.field_updated",
        )
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    # Two real changes (customer_name, customer_contact_email); the no-op
    # write to deal_name must NOT produce an event.
    assert len(events) == before_count + 2

    by_field = {next(iter(e.after_state.keys())): e for e in events[-2:]}
    assert "customer_name" in by_field
    assert by_field["customer_name"].before_state == {"customer_name": "Old Co"}
    assert by_field["customer_name"].after_state == {"customer_name": "New Co"}
    assert "customer_contact_email" in by_field
    assert by_field["customer_contact_email"].before_state == {"customer_contact_email": "old@example.com"}
    assert by_field["customer_contact_email"].after_state == {"customer_contact_email": "new@example.com"}
    # Actor is the system_admin who made the change
    assert all(e.actor_id == admin.id for e in events[-2:])


def test_partner_admin_patch_still_logs_legacy_event_not_field_updated(db_session):
    """Regression: partner_admin edits continue to log a single
    deal_registration.updated event, NOT per-field deal.field_updated
    events. The new audit shape applies only to internal admin edits."""
    org = make_org(db_session)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)  # draft
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Partner Renamed",
        })
        assert r.status_code == 200
    finally:
        clear_overrides()

    field_events = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.object_type == "deal_registration",
            AuditLog.object_id == deal.id,
            AuditLog.action == "deal.field_updated",
        )
        .count()
    )
    legacy_events = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.object_type == "deal_registration",
            AuditLog.object_id == deal.id,
            AuditLog.action == "deal_registration.updated",
        )
        .count()
    )
    assert field_events == 0
    assert legacy_events >= 1


def test_partner_admin_cannot_patch_submitted_deal(db_session):
    """Regression: partners still can't edit a submitted deal, even after
    the internal-admin escape hatch was added."""
    org = make_org(db_session)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id, status="submitted")
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Sneaky edit",
        })
        assert r.status_code == 400
        assert "draft" in r.json()["detail"].lower() or "submitted" in r.json()["detail"].lower()
    finally:
        clear_overrides()


def test_change_log_endpoint_returns_field_events_in_descending_order(db_session):
    """GET /internal/deals/{id}/change-log unpacks deal.field_updated events
    into flat field_name / old_value / new_value rows, newest first."""
    org = make_org(db_session)
    admin = make_user(UserRole.system_admin)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    deal = make_deal(db_session, org.id, status="approved")
    override_user(db_session, admin)
    client = TestClient(app)
    try:
        # Two sequential edits -> two events
        r1 = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Edit 1",
        })
        assert r1.status_code == 200, r1.text
        r2 = client.patch(f"/deal-registrations/{deal.id}", json={
            "customer_name": "Edit 2",
            "deal_notes": "Added note",
        })
        assert r2.status_code == 200, r2.text

        r = client.get(f"/internal/deals/{deal.id}/change-log")
        assert r.status_code == 200, r.text
        rows = r.json()
        # 1 (Edit 1) + 2 (Edit 2: customer_name + deal_notes) = 3 events
        assert len(rows) >= 3
        # Each row has the unpacked shape
        for row in rows:
            assert "timestamp" in row
            assert "field_name" in row
            assert "old_value" in row
            assert "new_value" in row
            assert row["actor_id"] == str(admin.id)
            assert row["actor_email"] == admin.email
        # Newest first -- the most recent edit was Edit 2 -> customer_name
        # went from "Edit 1" to "Edit 2"
        cust_rows = [r for r in rows if r["field_name"] == "customer_name"]
        assert len(cust_rows) >= 2
        assert cust_rows[0]["new_value"] == "Edit 2"
        assert cust_rows[0]["old_value"] == "Edit 1"
        assert cust_rows[1]["new_value"] == "Edit 1"
    finally:
        clear_overrides()


def test_change_log_endpoint_404_when_deal_missing(db_session):
    admin = make_user(UserRole.system_admin)
    override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get(f"/internal/deals/{uuid.uuid4()}/change-log")
        assert r.status_code == 404
    finally:
        clear_overrides()


def test_change_log_endpoint_blocks_partner(db_session):
    org = make_org(db_session)
    user = make_user(UserRole.partner_admin, partner_org_id=org.id)
    deal = make_deal(db_session, org.id)
    override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get(f"/internal/deals/{deal.id}/change-log")
        assert r.status_code == 403
    finally:
        clear_overrides()
