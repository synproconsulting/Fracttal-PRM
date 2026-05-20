"""Tests for Sprint 15 / FPRM-239 quoting data model and seed values."""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database import Base
import models  # noqa: F401  ensures all models register with Base.metadata
from models import (
    AddonCatalogItem,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    ProgramType,
    Quote,
    QuoteLineItem,
    QuoteVersion,
    User,
    VolumeDiscountTier,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_quote_models.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_quote_models.db"):
        try:
            os.remove("./test_quote_models.db")
        except OSError:
            pass


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def seed_pricing(db):
    """Seed pricing catalogue with the exact values from migration 023.

    Tests against this helper rather than relying on the live migration so they
    work with the in-memory ``Base.metadata.create_all`` test bootstrap.
    """
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter",      feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise",   feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1,   max_users=10,   transactional_user_discount_pct=Decimal("0"),  limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11,  max_users=50,   transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51,  max_users=100,  transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300,  transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500,  transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    addons = [
        ("first_tranche_assets",          "First Tranche of Assets",               Decimal("95.00"),  True,  True),
        ("second_tranche_assets",         "Second Tranche of Assets",              Decimal("55.00"),  True,  True),
        ("first_tranche_tasks",           "First Tranche of Tasks",                Decimal("95.00"),  True,  True),
        ("second_tranche_tasks",          "Second Tranche of Tasks",               Decimal("55.00"),  True,  True),
        ("transaction_log",               "Transaction Log",                       Decimal("95.00"),  True,  False),
        ("virtual_planner",               "Virtual Planner",                       Decimal("55.00"),  True,  True),
        ("trainable_ai_bot",              "Trainable Artificial Intelligence Bot", Decimal("95.00"),  False, True),
        ("budget",                        "Budget",                                Decimal("55.00"),  True,  False),
        ("maps",                          "Maps",                                  Decimal("55.00"),  True,  False),
        ("unlimited_request_users",       "Unlimited Request Users",               Decimal("95.00"),  False, True),
        ("unlimited_read_only_users",     "Unlimited Read-only Users",             Decimal("145.00"), False, True),
        ("advanced_warehouse",            "Advanced Warehouse Functionalities",    Decimal("95.00"),  False, True),
        ("guest_portal",                  "Guest Portal",                          Decimal("95.00"),  False, True),
        ("sharing_wo",                    "Sharing WO",                            Decimal("55.00"),  True,  False),
        ("advanced_apis",                 "Advanced APIs",                         Decimal("145.00"), True,  True),
        ("custom_request_portal",         "Custom Request Portal",                 Decimal("95.00"),  False, True),
        ("fracttal_hub",                  "FRACTTAL_HUB",                          Decimal("55.00"),  True,  True),
        ("fracttal_hub_cloud",            "FRACTTAL_HUB_CLOUD",                    Decimal("55.00"),  True,  True),
        ("automator_pro",                 "Automator Pro",                         Decimal("145.00"), True,  False),
        ("fracttal_bi_corp",              "Fracttal BI Corp",                      Decimal("95.00"),  True,  False),
        ("apis",                          "APIs",                                  Decimal("245.00"), False, True),
    ]
    for key, name, price, in_starter, in_pro in addons:
        db.add(AddonCatalogItem(
            addon_key=key, display_name=name, monthly_price=price,
            available_starter=in_starter, available_professional=in_pro,
            included_enterprise=True, is_active=True,
        ))
    db.commit()


def _make_user(db, role="channel_manager"):
    u = User(id=uuid.uuid4(), email=f"u-{uuid.uuid4().hex[:6]}@test.com",
             hashed_password="x", role=role, is_active=True)
    db.add(u)
    db.commit()
    return u


def _make_org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o)
    db.commit()
    return o


def _make_deal(db, org_id):
    """Create a minimal deal directly via SQL — DealRegistration FK fields covered."""
    from models import DealRegistration
    d = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=org_id,
        status="approved",
        customer_name="Test Customer",
        deal_name="Test Deal",
    )
    db.add(d)
    db.commit()
    return d


# ============================================================
# Tests
# ============================================================


def test_feature_plan_prices_seeded(db):
    seed_pricing(db)
    rows = db.query(FeaturePlanPrice).all()
    assert len(rows) == 3
    by_code = {r.plan_code: r for r in rows}
    assert by_code["enterprise"].feature_pack_annual == Decimal("8028.00")
    assert by_code["professional"].feature_pack_annual == Decimal("2868.00")
    assert by_code["starter"].feature_pack_annual == Decimal("1161.00")


def test_volume_discount_tiers_seeded(db):
    seed_pricing(db)
    rows = db.query(VolumeDiscountTier).order_by(VolumeDiscountTier.min_users).all()
    assert len(rows) == 6
    assert rows[1].min_users == 11
    assert rows[1].transactional_user_discount_pct == Decimal("30")
    assert rows[5].max_users is None
    assert rows[5].transactional_user_discount_pct == Decimal("70")


def test_addon_catalog_seeded(db):
    seed_pricing(db)
    rows = db.query(AddonCatalogItem).all()
    assert len(rows) == 21
    advanced_apis = db.query(AddonCatalogItem).filter_by(addon_key="advanced_apis").one()
    assert advanced_apis.available_starter is True
    assert advanced_apis.available_professional is True
    trainable_ai = db.query(AddonCatalogItem).filter_by(addon_key="trainable_ai_bot").one()
    assert trainable_ai.available_starter is False
    assert trainable_ai.available_professional is True


def test_addon_catalog_enterprise_included(db):
    seed_pricing(db)
    rows = db.query(AddonCatalogItem).all()
    assert all(r.included_enterprise is True for r in rows)


def test_quote_requires_deal_id(db):
    """A Quote cannot be created without a deal_id (NOT NULL constraint)."""
    user = _make_user(db)
    org = _make_org(db)
    bad = Quote(
        id=uuid.uuid4(),
        deal_id=None,                # violates NOT NULL
        partner_org_id=org.id,
        created_by=user.id,
        grand_total_after_discount=Decimal("0"),
        active_version=1,
        status="draft",
    )
    db.add(bad)
    with pytest.raises((IntegrityError, Exception)):
        db.commit()
    db.rollback()


def test_quote_version_fk_to_quote(db):
    """A QuoteVersion cannot exist without its parent quote.

    sqlite needs ``PRAGMA foreign_keys = ON`` per connection to enforce FKs.
    """
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = ON"))
    ver = QuoteVersion(
        id=uuid.uuid4(),
        quote_id=uuid.uuid4(),       # nonexistent quote id
        version_number=1,
        feature_plan="starter",
        qty_transactional_users=1,
        qty_limited_tech_users=0,
        selected_addons=[],
        grand_total_before_discount=Decimal("0"),
        grand_total_after_discount=Decimal("0"),
    )
    db.add(ver)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quote_line_item_fk_to_version(db):
    """A QuoteLineItem cannot exist without its parent version."""
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = ON"))
    line = QuoteLineItem(
        id=uuid.uuid4(),
        quote_version_id=uuid.uuid4(),  # nonexistent
        line_order=1,
        line_type="feature_pack",
        description="x",
        quantity=1,
        unit_price=Decimal("100"),
        total_before_discount=Decimal("100"),
        total_after_discount=Decimal("100"),
    )
    db.add(line)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quote_currency_defaults_to_usd(db):
    """Currency code defaults to USD when not specified."""
    user = _make_user(db)
    org = _make_org(db)
    deal = _make_deal(db, org.id)
    q = Quote(
        id=uuid.uuid4(),
        deal_id=deal.id,
        partner_org_id=org.id,
        created_by=user.id,
        active_version=1,
        status="draft",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    assert q.currency_code == "USD"


def test_quote_version_unique_constraint(db):
    """Two QuoteVersions with same (quote_id, version_number) raise."""
    user = _make_user(db)
    org = _make_org(db)
    deal = _make_deal(db, org.id)
    q = Quote(
        id=uuid.uuid4(), deal_id=deal.id, partner_org_id=org.id,
        created_by=user.id, active_version=1, status="draft",
    )
    db.add(q)
    db.commit()
    v1 = QuoteVersion(
        id=uuid.uuid4(), quote_id=q.id, version_number=1,
        feature_plan="enterprise", qty_transactional_users=1,
        qty_limited_tech_users=0, selected_addons=[],
        grand_total_before_discount=Decimal("0"),
        grand_total_after_discount=Decimal("0"),
    )
    v2 = QuoteVersion(
        id=uuid.uuid4(), quote_id=q.id, version_number=1,  # dup
        feature_plan="starter", qty_transactional_users=2,
        qty_limited_tech_users=0, selected_addons=[],
        grand_total_before_discount=Decimal("0"),
        grand_total_after_discount=Decimal("0"),
    )
    db.add(v1)
    db.commit()
    db.add(v2)
    with pytest.raises((IntegrityError, Exception)):
        db.commit()
    db.rollback()
