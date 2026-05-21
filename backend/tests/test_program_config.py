"""Sprint 13 — tests for /internal/config endpoints (FPRM-209 + FPRM-213).

Tests run against sqlite via Base.metadata.create_all — alembic migrations
do not run in CI. The seed rows that migration 021/022 install on Railway
are reproduced here in the `seeded_workflow_steps`, `seeded_tiers`, and
`seeded_activation_criteria` fixtures so the tests reflect production state.
"""
import os
import sys
import uuid

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
    ApprovalWorkflowStep,
    PartnerTierConfig,
    PartnerTierEligibilityRule,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_program_config.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_program_config.db"):
        try:
            os.remove("./test_program_config.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _make_user(db, role: UserRole) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture()
def seeded_workflow_steps(db_session):
    """Mirror migration 021 seed inserts."""
    rows = [
        ApprovalWorkflowStep(
            id=uuid.uuid4(),
            workflow_type="partner_application",
            step_order=1,
            step_name="Channel Ops Review",
            required_role=UserRole.channel_ops_admin.value,
            is_active=True,
        ),
        ApprovalWorkflowStep(
            id=uuid.uuid4(),
            workflow_type="deal_registration",
            step_order=1,
            step_name="Channel Manager Review",
            required_role=UserRole.channel_manager.value,
            is_active=True,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


# ---- Approval workflow step tests ----------------------------------------


def test_list_approval_steps(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.get("/internal/config/approval-steps")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    types = {i["workflow_type"] for i in items}
    assert types == {"partner_application", "deal_registration"}


def test_filter_by_workflow_type(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.get("/internal/config/approval-steps?workflow_type=deal_registration")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["workflow_type"] == "deal_registration"


def test_create_approval_step(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "partner_application",
        "step_order": 2,
        "step_name": "Channel Manager Sign-off",
        "required_role": "channel_manager",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["step_name"] == "Channel Manager Sign-off"
    assert body["step_order"] == 2


def test_create_step_invalid_workflow_type(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "banana",
        "step_order": 1,
        "step_name": "Whatever",
        "required_role": "channel_manager",
    })
    assert r.status_code == 400, r.text


def test_create_step_invalid_role(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "partner_application",
        "step_order": 1,
        "step_name": "Step",
        "required_role": "not_a_role",
    })
    assert r.status_code == 400, r.text


def test_patch_approval_step(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_workflow_steps[0]
    r = client.patch(f"/internal/config/approval-steps/{target.id}", json={
        "step_name": "Renamed Step",
    })
    assert r.status_code == 200, r.text
    assert r.json()["step_name"] == "Renamed Step"


def test_delete_approval_step_as_system_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    target = seeded_workflow_steps[1]
    r = client.delete(f"/internal/config/approval-steps/{target.id}")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    # After deletion, the row is filtered out of the list by default
    r2 = client.get("/internal/config/approval-steps")
    assert all(i["id"] != str(target.id) for i in r2.json()["items"])


def test_delete_forbidden_for_channel_ops_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_workflow_steps[0]
    r = client.delete(f"/internal/config/approval-steps/{target.id}")
    assert r.status_code == 403, r.text


def test_list_forbidden_for_partner_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.partner_admin))
    r = client.get("/internal/config/approval-steps")
    assert r.status_code == 403, r.text


def test_patch_unknown_step_returns_404(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.patch(
        f"/internal/config/approval-steps/{uuid.uuid4()}",
        json={"step_name": "X"},
    )
    assert r.status_code == 404, r.text


# ---- Tier + activation criteria tests (FPRM-213) -------------------------


@pytest.fixture()
def seeded_tiers(db_session):
    """Mirror migration 022 default tier seed."""
    rows = [
        PartnerTierConfig(id=uuid.uuid4(), tier_name="Registered", tier_rank=1,
                          description="Entry-level partner tier", is_active=True),
        PartnerTierConfig(id=uuid.uuid4(), tier_name="Silver", tier_rank=2,
                          description="Established partner", is_active=True),
        PartnerTierConfig(id=uuid.uuid4(), tier_name="Gold", tier_rank=3,
                          description="Top-tier partner", is_active=True),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


@pytest.fixture()
def seeded_activation_criteria(db_session):
    """Mirror migration 022 default activation criteria seed (6 rows)."""
    rows = [
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="profile_complete",
                                  is_required=True, is_active=True),
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="documents_uploaded",
                                  is_required=True, is_active=True),
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="baseline_training_complete",
                                  is_required=True, is_active=True),
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="terms_signed",
                                  is_required=True, is_active=True),
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="contract_signed",
                                  is_required=False, is_active=True),
        ActivationChecklistConfig(id=uuid.uuid4(), criterion_key="training_advanced_complete",
                                  is_required=False, is_active=True),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_list_tiers_includes_seed_data(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.get("/internal/config/tiers")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 3
    assert [t["tier_name"] for t in items] == ["Registered", "Silver", "Gold"]


def test_create_tier(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/tiers", json={
        "tier_name": "Platinum",
        "tier_rank": 4,
        "description": "Elite tier",
    })
    assert r.status_code == 201, r.text
    assert r.json()["tier_name"] == "Platinum"


def test_create_duplicate_tier_name_returns_409(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/tiers", json={
        "tier_name": "Gold",
        "tier_rank": 5,
    })
    assert r.status_code == 409, r.text


def test_patch_tier(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_tiers[0]
    r = client.patch(f"/internal/config/tiers/{target.id}", json={
        "description": "Updated description",
    })
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Updated description"


def test_add_eligibility_rule_to_tier(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.system_admin))
    tier = seeded_tiers[2]  # Gold
    r = client.post(
        f"/internal/config/tiers/{tier.id}/eligibility-rules",
        json={"rule_type": "min_deals_approved", "rule_value": "5",
              "description": "5 deals required"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rule_type"] == "min_deals_approved"
    assert body["rule_value"] == "5"

    # Confirm the tier list now reflects the rule
    r2 = client.get("/internal/config/tiers")
    gold = next(t for t in r2.json()["items"] if t["tier_name"] == "Gold")
    assert len(gold["eligibility_rules"]) == 1


def test_eligibility_rule_invalid_type_returns_400(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.system_admin))
    tier = seeded_tiers[1]
    r = client.post(
        f"/internal/config/tiers/{tier.id}/eligibility-rules",
        json={"rule_type": "bogus", "rule_value": "1"},
    )
    assert r.status_code == 400, r.text


def test_delete_eligibility_rule_system_admin_only(client, db_session, seeded_tiers):
    # System admin creates a rule then deletes it
    admin = _make_user(db_session, UserRole.system_admin)
    _as(admin)
    tier = seeded_tiers[1]
    create = client.post(
        f"/internal/config/tiers/{tier.id}/eligibility-rules",
        json={"rule_type": "min_revenue", "rule_value": "100000"},
    )
    assert create.status_code == 201
    rule_id = create.json()["id"]

    # channel_ops_admin should be 403
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    forbidden = client.delete(f"/internal/config/tiers/{tier.id}/eligibility-rules/{rule_id}")
    assert forbidden.status_code == 403, forbidden.text

    # system_admin can delete
    _as(admin)
    delete = client.delete(f"/internal/config/tiers/{tier.id}/eligibility-rules/{rule_id}")
    assert delete.status_code == 200, delete.text


def test_list_activation_criteria_includes_seed_data(client, db_session, seeded_activation_criteria):
    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.get("/internal/config/activation-criteria")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 6
    keys = {c["criterion_key"] for c in items}
    assert {"profile_complete", "documents_uploaded", "baseline_training_complete",
            "terms_signed", "contract_signed", "training_advanced_complete"} == keys


def test_create_activation_criterion(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/activation-criteria", json={
        "criterion_key": "compliance_review_done",
        "is_required": False,
        "description": "Compliance team has reviewed",
    })
    assert r.status_code == 201, r.text
    assert r.json()["criterion_key"] == "compliance_review_done"
    assert r.json()["is_required"] is False


def test_patch_activation_criterion(client, db_session, seeded_activation_criteria):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_activation_criteria[4]  # contract_signed (optional)
    r = client.patch(f"/internal/config/activation-criteria/{target.id}",
                     json={"is_required": True})
    assert r.status_code == 200, r.text
    assert r.json()["is_required"] is True


def test_soft_delete_activation_criterion(client, db_session, seeded_activation_criteria):
    _as(_make_user(db_session, UserRole.system_admin))
    target = seeded_activation_criteria[5]  # training_advanced_complete
    r = client.delete(f"/internal/config/activation-criteria/{target.id}")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    # Filter is_active=true should no longer include this row
    r2 = client.get("/internal/config/activation-criteria?is_active=true")
    assert all(c["id"] != str(target.id) for c in r2.json()["items"])


def test_tier_endpoints_forbidden_for_partner_role(client, db_session, seeded_tiers):
    _as(_make_user(db_session, UserRole.partner_admin))
    r = client.get("/internal/config/tiers")
    assert r.status_code == 403, r.text
    r2 = client.post("/internal/config/tiers", json={"tier_name": "X", "tier_rank": 9})
    assert r2.status_code == 403, r2.text


# ============================================================================
# Commission rates admin (post-Sprint 20 Phase 6 polish)
# ============================================================================


from decimal import Decimal as _Dec

from models import (
    AuditLog,
    CommissionStructure,
    CommissionYear,
    PartnerCategoryConfig,
)


@pytest.fixture()
def seeded_partner_category(db_session):
    """Reseller category row -- the FK target for commission rate inserts."""
    cat = PartnerCategoryConfig(
        id=uuid.uuid4(),
        code="reseller",
        display_name="Reseller",
        deal_reg_sla_hours=96,
        max_discount_pct=_Dec("20"),
        monthly_fee_usd=_Dec("200"),
        is_active=True,
    )
    db_session.add(cat)
    db_session.commit()
    return cat


@pytest.fixture()
def seeded_commission_rate(db_session, seeded_partner_category):
    rate = CommissionStructure(
        id=uuid.uuid4(),
        partner_category_code="reseller",
        commission_type="autonomous_sell",
        year=CommissionYear.year_1,
        commission_pct=_Dec("50"),
        subpartner_uplift_pct=_Dec("10"),
        applies_to_upsell=True,
        notes=None,
        is_active=True,
    )
    db_session.add(rate)
    db_session.commit()
    db_session.refresh(rate)
    return rate


def test_create_commission_rate_happy_path(client, db_session, seeded_partner_category):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "autonomous_sell",
        "year_label": "Year 1",
        "rate_pct": 50,
        "notes": "Standard reseller Y1",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["partner_category"] == "reseller"
    assert body["commission_type"] == "autonomous_sell"
    assert body["year"] == "year_1"
    assert body["year_label"] == "Year 1"
    assert body["rate_pct"] == 50.0
    assert body["notes"] == "Standard reseller Y1"
    assert body["is_active"] is True

    # Audit event written
    audit = db_session.query(AuditLog).filter_by(action="commission_rate.created").first()
    assert audit is not None
    assert audit.after_state["rate_pct"] == 50.0


def test_create_commission_rate_accepts_enum_code_year(client, db_session, seeded_partner_category):
    """year_label / year accept the enum code too, not just the display label."""
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "co_sell_shared",
        "year": "year_2_plus",
        "rate_pct": 15,
    })
    assert r.status_code == 201, r.text
    assert r.json()["year"] == "year_2_plus"


def test_create_commission_rate_rejects_unknown_partner_category(client, db_session):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "definitely_not_a_real_code",
        "commission_type": "autonomous_sell",
        "year_label": "Year 1",
        "rate_pct": 10,
    })
    assert r.status_code == 422
    assert "partner_category" in r.json()["detail"]


def test_create_commission_rate_rejects_bad_year_label(client, db_session, seeded_partner_category):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "autonomous_sell",
        "year_label": "next quarter",
        "rate_pct": 10,
    })
    assert r.status_code == 422


def test_create_commission_rate_rejects_out_of_range_pct(client, db_session, seeded_partner_category):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "autonomous_sell",
        "year_label": "Year 1",
        "rate_pct": 150,
    })
    assert r.status_code == 422


def test_create_commission_rate_rejects_duplicate_active_tuple(
    client, db_session, seeded_commission_rate,
):
    """The (category, type, year) tuple is what _snapshot_commission picks
    on, so duplicates would race."""
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "autonomous_sell",
        "year_label": "Year 1",
        "rate_pct": 55,
    })
    assert r.status_code == 409, r.text


def test_create_commission_rate_forbidden_for_channel_manager(
    client, db_session, seeded_partner_category,
):
    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.post("/internal/config/commission-rates", json={
        "partner_category": "reseller",
        "commission_type": "autonomous_sell",
        "year_label": "Year 1",
        "rate_pct": 50,
    })
    assert r.status_code == 403


def test_patch_commission_rate_updates_rate_and_notes(
    client, db_session, seeded_commission_rate,
):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.patch(
        f"/internal/config/commission-rates/{seeded_commission_rate.id}",
        json={"rate_pct": 45, "notes": "Bumped for promo"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rate_pct"] == 45.0
    assert body["notes"] == "Bumped for promo"

    audit = db_session.query(AuditLog).filter_by(action="commission_rate.updated").first()
    assert audit is not None
    assert audit.before_state["rate_pct"] == 50.0
    assert audit.after_state["rate_pct"] == 45.0


def test_patch_commission_rate_requires_at_least_one_field(
    client, db_session, seeded_commission_rate,
):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.patch(
        f"/internal/config/commission-rates/{seeded_commission_rate.id}",
        json={},
    )
    assert r.status_code == 422


def test_patch_commission_rate_404_on_missing(client, db_session):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.patch(
        f"/internal/config/commission-rates/{uuid.uuid4()}",
        json={"rate_pct": 10},
    )
    assert r.status_code == 404


def test_delete_commission_rate_soft_deletes_and_logs(
    client, db_session, seeded_commission_rate,
):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.delete(f"/internal/config/commission-rates/{seeded_commission_rate.id}")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    db_session.expire_all()
    refreshed = (
        db_session.query(CommissionStructure)
        .filter_by(id=seeded_commission_rate.id)
        .first()
    )
    assert refreshed is not None  # row still exists
    assert refreshed.is_active is False

    audit = db_session.query(AuditLog).filter_by(action="commission_rate.deleted").first()
    assert audit is not None
    assert audit.before_state["is_active"] is True
    assert audit.after_state["is_active"] is False


def test_delete_commission_rate_forbidden_for_channel_ops_admin(
    client, db_session, seeded_commission_rate,
):
    """DELETE is system_admin only -- channel_ops_admin can edit but not
    retire rates."""
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.delete(f"/internal/config/commission-rates/{seeded_commission_rate.id}")
    assert r.status_code == 403


def test_list_commission_rates_default_excludes_inactive(
    client, db_session, seeded_commission_rate,
):
    # Soft-delete the seeded rate
    seeded_commission_rate.is_active = False
    db_session.commit()
    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.get("/internal/config/commission-rates")
    assert r.status_code == 200
    assert all(it["is_active"] for it in r.json()["items"])
    assert len(r.json()["items"]) == 0


def test_list_commission_rates_include_inactive_returns_all(
    client, db_session, seeded_commission_rate,
):
    seeded_commission_rate.is_active = False
    db_session.commit()
    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.get("/internal/config/commission-rates?include_inactive=true")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["is_active"] is False


def test_list_commission_rates_filters_by_partner_category(
    client, db_session, seeded_commission_rate, seeded_partner_category,
):
    # Add a second category + rate
    master = PartnerCategoryConfig(
        id=uuid.uuid4(),
        code="master",
        display_name="Master",
        deal_reg_sla_hours=72,
        max_discount_pct=_Dec("25"),
        monthly_fee_usd=_Dec("400"),
        is_active=True,
    )
    db_session.add(master)
    db_session.add(CommissionStructure(
        id=uuid.uuid4(),
        partner_category_code="master",
        commission_type="autonomous_sell",
        year=CommissionYear.year_1,
        commission_pct=_Dec("60"),
        subpartner_uplift_pct=_Dec("10"),
        applies_to_upsell=True,
        is_active=True,
    ))
    db_session.commit()

    _as(_make_user(db_session, UserRole.channel_manager))
    r = client.get("/internal/config/commission-rates?partner_category=reseller")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["partner_category"] == "reseller"


def test_list_commission_rates_forbidden_for_partner(client, db_session):
    _as(_make_user(db_session, UserRole.partner_admin))
    r = client.get("/internal/config/commission-rates")
    assert r.status_code == 403
