"""Tests for Sprint 15 / FPRM-243 quote calculation engine.

Verifies the engine matches the four worked examples in the Fracttal Pricing
and Quotation Specification exactly, plus boundary and error paths.
"""
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base
import models  # noqa: F401
from models import AddonCatalogItem, FeaturePlanPrice, VolumeDiscountTier
from quote_engine import (
    PLAN_DISPLAY_NAMES,
    QuoteCalculationResult,
    QuoteLineItemData,
    calculate_quote,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_quote_engine.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_quote_engine.db"):
        try:
            os.remove("./test_quote_engine.db")
        except OSError:
            pass


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "addon_catalog_items", "volume_discount_tiers", "feature_plan_prices",
        ):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


def seed_pricing(db):
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
    for key, name, price, in_starter, in_pro in [
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
    ]:
        db.add(AddonCatalogItem(
            addon_key=key, display_name=name, monthly_price=price,
            available_starter=in_starter, available_professional=in_pro,
            included_enterprise=True, is_active=True,
        ))
    db.commit()


def _by_type(result: QuoteCalculationResult, line_type: str) -> list[QuoteLineItemData]:
    return [l for l in result.line_items if l.line_type == line_type]


# ============================================================
# Spec example 1: Enterprise, 5 trans, 25 ltd-tech, 0% discount
# ============================================================
def test_spec_example_1_enterprise_no_discount(db):
    r = calculate_quote(
        db, feature_plan="enterprise",
        feature_plan_discount_pct=0,
        qty_transactional=5, qty_limited_tech_quoted=25,
        selected_addon_keys=[],
    )
    # Feature Pack
    fp = _by_type(r, "feature_pack")[0]
    assert fp.quantity == 1
    assert fp.unit_price == Decimal("8028.00")
    assert fp.discount_pct == Decimal("0")
    assert fp.total_after_discount == Decimal("8028.00")

    # Transactional Users — 5 fit in band 1 (1-10, 0%)
    tu = _by_type(r, "transactional_user")
    assert len(tu) == 1
    assert tu[0].quantity == 5
    assert tu[0].unit_price == Decimal("900.00")
    assert tu[0].discount_pct == Decimal("0")
    assert tu[0].total_after_discount == Decimal("4500.00")

    # Free allocation — 5 free (qty_transactional = 5)
    fa = _by_type(r, "free_allocation")
    assert len(fa) == 1
    assert fa[0].quantity == 5
    assert fa[0].total_after_discount == Decimal("0.00")

    # Limited Tech priced = 25 - 5 = 20 → band 1 (qty=10 at 0%) + band 2 (qty=10 at 30%)
    ltu = _by_type(r, "limited_tech_user")
    assert len(ltu) == 2
    assert ltu[0].quantity == 10
    assert ltu[0].discount_pct == Decimal("0")
    assert ltu[0].total_after_discount == Decimal("2400.00")
    assert ltu[1].quantity == 10
    assert ltu[1].discount_pct == Decimal("30")
    assert ltu[1].total_after_discount == Decimal("1680.00")

    assert r.grand_total_before_discount == Decimal("17328.00")
    assert r.grand_total_after_discount == Decimal("16608.00")


# ============================================================
# Spec example 2: Enterprise, 5 trans, 25 ltd-tech, 30% discount
# ============================================================
def test_spec_example_2_enterprise_with_discount(db):
    r = calculate_quote(
        db, feature_plan="enterprise",
        feature_plan_discount_pct=30,
        qty_transactional=5, qty_limited_tech_quoted=25,
        selected_addon_keys=[],
    )
    # Feature pack at 30% off: 8028 * 0.7 = 5619.60
    fp = _by_type(r, "feature_pack")[0]
    assert fp.discount_pct == Decimal("30")
    assert fp.total_after_discount == Decimal("5619.60")

    # No free allocation when discount applied
    assert _by_type(r, "free_allocation") == []

    # All 25 LT users priced — band 1 (10 at 0%) + band 2 (15 at 30%)
    ltu = _by_type(r, "limited_tech_user")
    assert len(ltu) == 2
    assert ltu[0].quantity == 10
    assert ltu[0].discount_pct == Decimal("0")
    assert ltu[0].total_after_discount == Decimal("2400.00")
    assert ltu[1].quantity == 15
    assert ltu[1].discount_pct == Decimal("30")
    # 240 * 15 = 3600; * 0.7 = 2520.00
    assert ltu[1].total_after_discount == Decimal("2520.00")

    # 8028 + 4500 + 2400 + 3600 = 18528
    assert r.grand_total_before_discount == Decimal("18528.00")
    # 5619.60 + 4500 + 2400 + 2520 = 15039.60
    assert r.grand_total_after_discount == Decimal("15039.60")


# ============================================================
# Spec example 3: Professional, 3 trans, 8 ltd-tech, 0%, advanced_warehouse
# ============================================================
def test_spec_example_3_professional_with_addon(db):
    r = calculate_quote(
        db, feature_plan="professional",
        feature_plan_discount_pct=0,
        qty_transactional=3, qty_limited_tech_quoted=8,
        selected_addon_keys=["advanced_warehouse"],
    )
    fp = _by_type(r, "feature_pack")[0]
    assert fp.total_after_discount == Decimal("2868.00")
    assert _by_type(r, "transactional_user")[0].total_after_discount == Decimal("2160.00")

    fa = _by_type(r, "free_allocation")[0]
    assert fa.quantity == 3

    # Limited tech priced = 8 - 3 = 5 in band 1 at 0% = 1200
    ltu = _by_type(r, "limited_tech_user")
    assert len(ltu) == 1
    assert ltu[0].quantity == 5
    assert ltu[0].total_after_discount == Decimal("1200.00")

    # Add-on: 95 * 12 = 1140
    addons = _by_type(r, "addon")
    assert len(addons) == 1
    assert addons[0].addon_key == "advanced_warehouse"
    assert addons[0].total_after_discount == Decimal("1140.00")

    assert r.grand_total_before_discount == Decimal("7368.00")
    assert r.grand_total_after_discount == Decimal("7368.00")


# ============================================================
# Spec example 4: Professional, 3 trans, 8 ltd-tech, 30%, advanced_warehouse
# ============================================================
def test_spec_example_4_professional_discount_with_addon(db):
    r = calculate_quote(
        db, feature_plan="professional",
        feature_plan_discount_pct=30,
        qty_transactional=3, qty_limited_tech_quoted=8,
        selected_addon_keys=["advanced_warehouse"],
    )
    # 2868 * 0.7 = 2007.60
    assert _by_type(r, "feature_pack")[0].total_after_discount == Decimal("2007.60")
    assert _by_type(r, "transactional_user")[0].total_after_discount == Decimal("2160.00")

    # No free allocation
    assert _by_type(r, "free_allocation") == []
    # All 8 LT priced in band 1 at 0%
    ltu = _by_type(r, "limited_tech_user")
    assert len(ltu) == 1
    assert ltu[0].quantity == 8
    assert ltu[0].total_after_discount == Decimal("1920.00")

    assert _by_type(r, "addon")[0].total_after_discount == Decimal("1140.00")

    assert r.grand_total_before_discount == Decimal("8088.00")
    assert r.grand_total_after_discount == Decimal("7227.60")


# ============================================================
# Additional unit cases
# ============================================================
def test_starter_plan_with_addon(db):
    r = calculate_quote(
        db, feature_plan="starter", feature_plan_discount_pct=0,
        qty_transactional=2, qty_limited_tech_quoted=2,
        selected_addon_keys=["fracttal_hub"],
    )
    assert _by_type(r, "addon")[0].total_after_discount == Decimal("660.00")  # 55*12
    assert _by_type(r, "feature_pack")[0].total_after_discount == Decimal("1161.00")


def test_enterprise_with_addons_raises(db):
    with pytest.raises(ValueError, match="Enterprise"):
        calculate_quote(
            db, feature_plan="enterprise", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=["fracttal_hub"],
        )


def test_zero_limited_tech_users(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=5, qty_limited_tech_quoted=0,
        selected_addon_keys=[],
    )
    assert _by_type(r, "limited_tech_user") == []
    assert _by_type(r, "free_allocation") == []
    # Only FP + 1 trans line
    assert r.grand_total_after_discount == Decimal("8028.00") + Decimal("4500.00")


def test_free_allocation_capped_at_requested(db):
    """If free_limited_tech > qty requested, free qty is capped."""
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=10, qty_limited_tech_quoted=3,
        selected_addon_keys=[],
    )
    fa = _by_type(r, "free_allocation")
    assert len(fa) == 1
    assert fa[0].quantity == 3
    # No priced LT users
    assert _by_type(r, "limited_tech_user") == []


def test_volume_band_boundary_exactly_10(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=10, qty_limited_tech_quoted=0,
        selected_addon_keys=[],
    )
    tu = _by_type(r, "transactional_user")
    assert len(tu) == 1
    assert tu[0].quantity == 10
    assert tu[0].discount_pct == Decimal("0")


def test_volume_band_boundary_11_splits(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=11, qty_limited_tech_quoted=0,
        selected_addon_keys=[],
    )
    tu = _by_type(r, "transactional_user")
    assert len(tu) == 2
    assert tu[0].quantity == 10 and tu[0].discount_pct == Decimal("0")
    assert tu[1].quantity == 1  and tu[1].discount_pct == Decimal("30")


def test_volume_band_501_uses_70pct(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=501, qty_limited_tech_quoted=0,
        selected_addon_keys=[],
    )
    tu = _by_type(r, "transactional_user")
    # Bands: 10 (0%) + 40 (30%) + 50 (40%) + 200 (50%) + 200 (60%) + 1 (70%)
    assert len(tu) == 6
    assert tu[-1].quantity == 1
    assert tu[-1].discount_pct == Decimal("70")


def test_feature_plan_discount_100pct(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=100,
        qty_transactional=3, qty_limited_tech_quoted=0,
        selected_addon_keys=[],
    )
    fp = _by_type(r, "feature_pack")[0]
    assert fp.total_after_discount == Decimal("0.00")
    tu = _by_type(r, "transactional_user")[0]
    # User line unaffected by the feature-plan discount
    assert tu.total_after_discount == Decimal("2700.00")


def test_decimal_precision(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=30,
        qty_transactional=5, qty_limited_tech_quoted=25,
        selected_addon_keys=[],
    )
    for line in r.line_items:
        assert line.unit_price.as_tuple().exponent >= -2
        assert line.total_before_discount.as_tuple().exponent >= -2
        assert line.total_after_discount.as_tuple().exponent >= -2


def test_grand_total_equals_sum_of_lines(db):
    r = calculate_quote(
        db, feature_plan="professional", feature_plan_discount_pct=15,
        qty_transactional=7, qty_limited_tech_quoted=20,
        selected_addon_keys=["fracttal_hub", "virtual_planner"],
    )
    expected_after = sum((l.total_after_discount for l in r.line_items), Decimal("0"))
    expected_before = sum((l.total_before_discount for l in r.line_items), Decimal("0"))
    assert r.grand_total_after_discount == expected_after.quantize(Decimal("0.01"))
    assert r.grand_total_before_discount == expected_before.quantize(Decimal("0.01"))


def test_unknown_addon_key_raises(db):
    with pytest.raises(ValueError, match="Unknown add-on"):
        calculate_quote(
            db, feature_plan="starter", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=["nonexistent_addon"],
        )


def test_addon_unavailable_for_starter_raises(db):
    """trainable_ai_bot is professional-only."""
    with pytest.raises(ValueError, match="Starter"):
        calculate_quote(
            db, feature_plan="starter", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=["trainable_ai_bot"],
        )


def test_invalid_plan_raises(db):
    with pytest.raises(ValueError, match="Invalid feature plan"):
        calculate_quote(
            db, feature_plan="gold", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=[],
        )


def test_professional_addon_marked_unavailable_raises(db):
    """transaction_log is starter-only in the catalogue."""
    with pytest.raises(ValueError, match="Professional"):
        calculate_quote(
            db, feature_plan="professional", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=["transaction_log"],
        )


def test_multiple_addons_yield_separate_lines(db):
    r = calculate_quote(
        db, feature_plan="starter", feature_plan_discount_pct=0,
        qty_transactional=1, qty_limited_tech_quoted=0,
        selected_addon_keys=["fracttal_hub", "virtual_planner", "first_tranche_assets"],
    )
    addons = _by_type(r, "addon")
    assert len(addons) == 3
    keys = [a.addon_key for a in addons]
    assert keys == ["fracttal_hub", "virtual_planner", "first_tranche_assets"]
    totals = {a.addon_key: a.total_after_discount for a in addons}
    assert totals["fracttal_hub"] == Decimal("660.00")          # 55*12
    assert totals["virtual_planner"] == Decimal("660.00")        # 55*12
    assert totals["first_tranche_assets"] == Decimal("1140.00")  # 95*12


def test_line_order_is_sequential(db):
    r = calculate_quote(
        db, feature_plan="enterprise", feature_plan_discount_pct=0,
        qty_transactional=15, qty_limited_tech_quoted=12,
        selected_addon_keys=[],
    )
    orders = [l.line_order for l in r.line_items]
    assert orders == list(range(1, len(orders) + 1))


def test_addon_only_on_starter_disallowed_for_professional(db):
    """budget is starter-only, available_professional=False."""
    with pytest.raises(ValueError):
        calculate_quote(
            db, feature_plan="professional", feature_plan_discount_pct=0,
            qty_transactional=1, qty_limited_tech_quoted=0,
            selected_addon_keys=["budget"],
        )
