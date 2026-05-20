"""Sprint 15 / FPRM-243 — Fracttal software pricing quote calculation engine.

Single source of truth for software pricing calculations (AD-16). No FastAPI
imports; no router imports. Importable standalone by tests without spinning up
the app. The router layer in ``quotes_router`` wraps :func:`calculate_quote`
and catches :class:`ValueError` to convert to HTTP 422.

Rules implemented (per the Fracttal Pricing and Quotation Specification):

1. **Free Limited Technician allocation.** Customers receive one free Limited
   Technician licence per Transactional User purchased, **provided the Feature
   Plan discount is 0%**. Any Feature Plan discount suppresses the free
   allocation entirely.
2. **Volume discount banding.** Transactional and Limited Technician user
   counts are split across the 6 volume bands (1-10, 11-50, ..., 500+) with
   one line item per non-zero band carrying that band's discount.
3. **Feature Plan discount.** Applies to the Feature Pack line only — NOT to
   user licences or add-ons.
4. **Add-ons.** One line per selected add-on; annual cost = monthly * 12.
   Enterprise plan: no add-ons allowed (everything is included).
   Add-on must be marked available for the selected plan or a ``ValueError``
   is raised.

All monetary amounts use :class:`decimal.Decimal` quantised to 2 places to
avoid floating-point drift. Pricing data is read live from
``feature_plan_prices``, ``volume_discount_tiers``, and ``addon_catalog_items``
so admins can adjust pricing without redeploying.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from models import AddonCatalogItem, FeaturePlanPrice, VolumeDiscountTier


PLAN_DISPLAY_NAMES = {
    "starter": "Starter",
    "professional": "Professional",
    "enterprise": "Enterprise",
}


@dataclass
class QuoteLineItemData:
    """One row in a calculated quote. Persisted to ``quote_line_items``."""

    line_order: int
    line_type: str
    description: str
    quantity: int
    unit_price: Decimal
    discount_pct: Decimal
    total_before_discount: Decimal
    total_after_discount: Decimal
    addon_key: Optional[str] = None


@dataclass
class QuoteCalculationResult:
    """Engine output. Persisted to ``quote_versions`` + ``quote_line_items``."""

    line_items: list[QuoteLineItemData] = field(default_factory=list)
    grand_total_before_discount: Decimal = Decimal("0.00")
    grand_total_after_discount: Decimal = Decimal("0.00")


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _apply_volume_bands(
    total_qty: int,
    unit_price: Decimal,
    tiers: list[VolumeDiscountTier],
    line_type: str,
    description: str,
    start_order: int,
) -> list[QuoteLineItemData]:
    """Split ``total_qty`` across volume bands, emitting one line per non-zero
    band carrying that band's discount.

    ``tiers`` are sorted by ``min_users`` asc. Unbounded top band
    (``max_users is None``) absorbs all remaining quantity.
    """
    lines: list[QuoteLineItemData] = []
    remaining = total_qty
    order = start_order
    sorted_tiers = sorted(tiers, key=lambda t: t.min_users)
    for tier in sorted_tiers:
        if remaining <= 0:
            break
        if line_type == "transactional_user":
            discount_pct = Decimal(str(tier.transactional_user_discount_pct))
        else:
            discount_pct = Decimal(str(tier.limited_tech_user_discount_pct))
        band_capacity = (
            tier.max_users - tier.min_users + 1
            if tier.max_users is not None
            else remaining
        )
        band_qty = min(remaining, band_capacity)
        if band_qty > 0:
            total_before = _round2(unit_price * band_qty)
            total_after = _round2(total_before * (Decimal("1") - discount_pct / Decimal("100")))
            lines.append(
                QuoteLineItemData(
                    line_order=order,
                    line_type=line_type,
                    description=description,
                    quantity=band_qty,
                    unit_price=unit_price,
                    discount_pct=discount_pct,
                    total_before_discount=total_before,
                    total_after_discount=total_after,
                    addon_key=None,
                )
            )
            order += 1
        remaining -= band_qty
    return lines


def calculate_quote(
    db: Session,
    feature_plan: str,
    feature_plan_discount_pct: float,
    qty_transactional: int,
    qty_limited_tech_quoted: int,
    selected_addon_keys: list[str],
) -> QuoteCalculationResult:
    """Calculate a software pricing quote per the Fracttal spec.

    Reads pricing data live from the database. Raises :class:`ValueError` on
    any validation failure (unknown plan, add-on not allowed for the plan,
    unknown add-on key). The router layer catches these and converts to
    HTTP 422.

    Args:
        db: active SQLAlchemy session.
        feature_plan: ``"starter"`` | ``"professional"`` | ``"enterprise"``.
        feature_plan_discount_pct: 0-100. Applies ONLY to the Feature Pack.
        qty_transactional: number of Transactional User licences.
        qty_limited_tech_quoted: total Limited Technician User licences
            requested (BEFORE the free allocation is netted out).
        selected_addon_keys: add-on keys; must be available for the selected
            plan; ignored for enterprise (which raises if any are passed).
    """
    if feature_plan not in PLAN_DISPLAY_NAMES:
        raise ValueError(f"Invalid feature plan: {feature_plan!r}")

    if feature_plan == "enterprise" and selected_addon_keys:
        raise ValueError(
            "Enterprise plan includes all features - add-ons cannot be selected"
        )

    plan_display = PLAN_DISPLAY_NAMES[feature_plan]
    discount_pct = Decimal(str(feature_plan_discount_pct))

    plan_price: FeaturePlanPrice | None = (
        db.query(FeaturePlanPrice)
        .filter(
            FeaturePlanPrice.plan_code == feature_plan,
            FeaturePlanPrice.is_active.is_(True),
        )
        .order_by(FeaturePlanPrice.effective_from.desc())
        .first()
    )
    if plan_price is None:
        raise ValueError(f"No active pricing row for plan: {feature_plan!r}")

    tiers = (
        db.query(VolumeDiscountTier)
        .filter(VolumeDiscountTier.is_active.is_(True))
        .all()
    )

    # --- Free Limited Tech allocation rule ---
    free_limited_tech = qty_transactional if discount_pct == 0 else 0
    qty_limited_tech_to_price = max(0, qty_limited_tech_quoted - free_limited_tech)

    lines: list[QuoteLineItemData] = []
    order = 1

    # --- Line 1: Feature Pack (the only line affected by feature_plan_discount_pct) ---
    fp_unit = Decimal(str(plan_price.feature_pack_annual))
    fp_total_before = _round2(fp_unit)
    fp_total_after = _round2(fp_total_before * (Decimal("1") - discount_pct / Decimal("100")))
    lines.append(
        QuoteLineItemData(
            line_order=order,
            line_type="feature_pack",
            description=f"Fracttal One CMMS - {plan_display} Plan (Annual Payment)",
            quantity=1,
            unit_price=fp_unit,
            discount_pct=discount_pct,
            total_before_discount=fp_total_before,
            total_after_discount=fp_total_after,
        )
    )
    order += 1

    # --- Transactional User lines (volume-banded) ---
    if qty_transactional > 0:
        trans_unit = Decimal(str(plan_price.transactional_user_annual))
        trans_lines = _apply_volume_bands(
            total_qty=qty_transactional,
            unit_price=trans_unit,
            tiers=tiers,
            line_type="transactional_user",
            description=f"Transactional Users - {plan_display} Plan (Annual Payment)",
            start_order=order,
        )
        lines.extend(trans_lines)
        order += len(trans_lines)

    # --- Free Limited Tech allocation line (only if any free allocation is consumed) ---
    actual_free = min(free_limited_tech, qty_limited_tech_quoted)
    if actual_free > 0:
        lines.append(
            QuoteLineItemData(
                line_order=order,
                line_type="free_allocation",
                description=(
                    f"Limited Technician Users - {plan_display} Plan "
                    "(Annual Payment) [Complimentary]"
                ),
                quantity=actual_free,
                unit_price=Decimal("0.00"),
                discount_pct=Decimal("0.00"),
                total_before_discount=Decimal("0.00"),
                total_after_discount=Decimal("0.00"),
            )
        )
        order += 1

    # --- Limited Tech User priced lines (banded on qty_limited_tech_to_price) ---
    if qty_limited_tech_to_price > 0:
        ltd_unit = Decimal(str(plan_price.limited_tech_user_annual))
        ltd_lines = _apply_volume_bands(
            total_qty=qty_limited_tech_to_price,
            unit_price=ltd_unit,
            tiers=tiers,
            line_type="limited_tech_user",
            description=f"Limited Technician Users - {plan_display} Plan (Annual Payment)",
            start_order=order,
        )
        lines.extend(ltd_lines)
        order += len(ltd_lines)

    # --- Add-on lines ---
    for addon_key in selected_addon_keys:
        addon: AddonCatalogItem | None = (
            db.query(AddonCatalogItem)
            .filter(
                AddonCatalogItem.addon_key == addon_key,
                AddonCatalogItem.is_active.is_(True),
            )
            .first()
        )
        if addon is None:
            raise ValueError(f"Unknown add-on key: {addon_key!r}")
        if feature_plan == "starter" and not addon.available_starter:
            raise ValueError(
                f"Add-on {addon_key!r} is not available for Starter plan"
            )
        if feature_plan == "professional" and not addon.available_professional:
            raise ValueError(
                f"Add-on {addon_key!r} is not available for Professional plan"
            )
        annual_price = _round2(Decimal(str(addon.monthly_price)) * Decimal("12"))
        lines.append(
            QuoteLineItemData(
                line_order=order,
                line_type="addon",
                description=addon.display_name,
                quantity=1,
                unit_price=annual_price,
                discount_pct=Decimal("0.00"),
                total_before_discount=annual_price,
                total_after_discount=annual_price,
                addon_key=addon_key,
            )
        )
        order += 1

    grand_before = _round2(sum((l.total_before_discount for l in lines), Decimal("0")))
    grand_after = _round2(sum((l.total_after_discount for l in lines), Decimal("0")))

    return QuoteCalculationResult(
        line_items=lines,
        grand_total_before_discount=grand_before,
        grand_total_after_discount=grand_after,
    )
