"""Sprint 19 / FPRM-300 — Pricing catalogue admin CRUD API (AD-25).

Write side for the three pricing-catalogue tables that drive the quote engine:

* ``feature_plan_prices``  — per-plan annual list prices
* ``volume_discount_tiers`` — user-count discount bands
* ``addon_catalog_items``  — add-on catalogue

The matching read-side GETs for plans + addons live in
``quotes_router.py`` (extended with ``?include_inactive=true`` for admins);
``GET /internal/config/pricing/volume-tiers`` is defined here because the
quote engine reads volume tiers directly from the DB and never returns them
to the quote form.

Auth (matches FPRM-209/213 program-config conventions):

* GET     — any internal authenticated user; ``?include_inactive=true`` is
            admin-only (channel_ops_admin / system_admin).
* POST    — channel_ops_admin or system_admin.
* PATCH   — channel_ops_admin or system_admin.
* DELETE  — system_admin only (soft delete = ``is_active = False``).

Every write logs an audit event with action ``pricing.<entity>_<verb>`` so
Story 3's ``/admin/audit-log?action_prefix=pricing`` history panel can render
the change timeline.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user
from database import get_db
from models import AddonCatalogItem, FeaturePlanPrice, User, VolumeDiscountTier
from roles import UserRole


router = APIRouter(tags=["pricing-admin"])


ADMIN_ROLES = {UserRole.channel_ops_admin.value, UserRole.system_admin.value}
SYSTEM_ADMIN = UserRole.system_admin.value
VALID_PLAN_CODES = {"starter", "professional", "enterprise"}


def _require_admin(user: User) -> None:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Requires channel_ops_admin or system_admin role",
        )


def _require_system_admin(user: User) -> None:
    if user.role != SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="Requires system_admin role")


def _serialise_plan(r: FeaturePlanPrice) -> dict:
    return {
        "id": str(r.id),
        "plan_code": r.plan_code,
        "feature_pack_annual": str(r.feature_pack_annual),
        "transactional_user_annual": str(r.transactional_user_annual),
        "limited_tech_user_annual": str(r.limited_tech_user_annual),
        "effective_from": r.effective_from.isoformat(),
        "is_active": r.is_active,
    }


def _serialise_tier(r: VolumeDiscountTier) -> dict:
    return {
        "id": str(r.id),
        "min_users": r.min_users,
        "max_users": r.max_users,
        "transactional_user_discount_pct": str(r.transactional_user_discount_pct),
        "limited_tech_user_discount_pct": str(r.limited_tech_user_discount_pct),
        "is_active": r.is_active,
    }


def _serialise_addon(r: AddonCatalogItem) -> dict:
    return {
        "id": str(r.id),
        "addon_key": r.addon_key,
        "display_name": r.display_name,
        "monthly_price": str(r.monthly_price),
        "available_starter": r.available_starter,
        "available_professional": r.available_professional,
        "included_enterprise": r.included_enterprise,
        "is_active": r.is_active,
    }


# ============================================================
# Feature Plan Price write endpoints
# ============================================================


@router.post("/internal/config/pricing/plans", status_code=201)
def create_plan_price(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    plan_code = body.get("plan_code")
    if plan_code not in VALID_PLAN_CODES:
        raise HTTPException(
            status_code=422,
            detail=f"plan_code must be one of {sorted(VALID_PLAN_CODES)}",
        )
    required = ("feature_pack_annual", "transactional_user_annual", "limited_tech_user_annual", "effective_from")
    missing = [f for f in required if body.get(f) in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required field(s): {missing}")
    try:
        effective_from = date.fromisoformat(body["effective_from"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="effective_from must be ISO 8601 (YYYY-MM-DD)")
    row = FeaturePlanPrice(
        id=uuid.uuid4(),
        plan_code=plan_code,
        feature_pack_annual=body["feature_pack_annual"],
        transactional_user_annual=body["transactional_user_annual"],
        limited_tech_user_annual=body["limited_tech_user_annual"],
        effective_from=effective_from,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.plan_price_created",
        object_type="feature_plan_price",
        object_id=row.id,
        after={"plan_code": plan_code, "effective_from": effective_from.isoformat()},
    )
    return _serialise_plan(row)


@router.patch("/internal/config/pricing/plans/{plan_price_id}")
def update_plan_price(
    plan_price_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = db.query(FeaturePlanPrice).filter(FeaturePlanPrice.id == plan_price_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Plan price not found")
    before = {
        "feature_pack_annual": str(row.feature_pack_annual),
        "transactional_user_annual": str(row.transactional_user_annual),
        "limited_tech_user_annual": str(row.limited_tech_user_annual),
        "effective_from": row.effective_from.isoformat(),
        "is_active": row.is_active,
    }
    for field in ("feature_pack_annual", "transactional_user_annual", "limited_tech_user_annual"):
        if field in body and body[field] is not None:
            setattr(row, field, body[field])
    if "effective_from" in body and body["effective_from"]:
        try:
            row.effective_from = date.fromisoformat(body["effective_from"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="effective_from must be ISO 8601")
    if "is_active" in body and body["is_active"] is not None:
        row.is_active = bool(body["is_active"])
    db.commit()
    db.refresh(row)
    after = {
        "feature_pack_annual": str(row.feature_pack_annual),
        "transactional_user_annual": str(row.transactional_user_annual),
        "limited_tech_user_annual": str(row.limited_tech_user_annual),
        "effective_from": row.effective_from.isoformat(),
        "is_active": row.is_active,
    }
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.plan_price_updated",
        object_type="feature_plan_price",
        object_id=row.id,
        before=before,
        after=after,
    )
    return _serialise_plan(row)


@router.delete("/internal/config/pricing/plans/{plan_price_id}")
def deactivate_plan_price(
    plan_price_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_system_admin(current_user)
    row = db.query(FeaturePlanPrice).filter(FeaturePlanPrice.id == plan_price_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Plan price not found")
    active_count = (
        db.query(func.count(FeaturePlanPrice.id))
        .filter(FeaturePlanPrice.plan_code == row.plan_code)
        .filter(FeaturePlanPrice.is_active.is_(True))
        .scalar()
    )
    if row.is_active and active_count <= 1:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot deactivate the last active price row for plan "
                f"'{row.plan_code}'. Add a replacement row first."
            ),
        )
    row.is_active = False
    db.commit()
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.plan_price_deactivated",
        object_type="feature_plan_price",
        object_id=row.id,
    )
    return {"id": str(row.id), "is_active": False}


# ============================================================
# Volume Discount Tier endpoints
# ============================================================


@router.get("/internal/config/pricing/volume-tiers")
def list_volume_tiers(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if include_inactive and current_user.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Only channel_ops_admin or system_admin can view inactive pricing rows",
        )
    query = db.query(VolumeDiscountTier)
    if not include_inactive:
        query = query.filter(VolumeDiscountTier.is_active.is_(True))
    rows = query.order_by(VolumeDiscountTier.min_users).all()
    return [_serialise_tier(r) for r in rows]


def _check_tier_overlap(
    db: Session,
    min_users: int,
    max_users: Optional[int],
    exclude_id: Optional[uuid.UUID] = None,
) -> None:
    """422 if the proposed band intersects any other active tier."""
    if min_users is None or min_users < 1:
        raise HTTPException(status_code=422, detail="min_users must be >= 1")
    if max_users is not None and max_users < min_users:
        raise HTTPException(status_code=422, detail="max_users must be >= min_users")
    new_top = max_users if max_users is not None else float("inf")
    others = db.query(VolumeDiscountTier).filter(VolumeDiscountTier.is_active.is_(True))
    if exclude_id is not None:
        others = others.filter(VolumeDiscountTier.id != exclude_id)
    for tier in others.all():
        tier_top = tier.max_users if tier.max_users is not None else float("inf")
        if min_users <= tier_top and new_top >= tier.min_users:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"New tier ({min_users}-{max_users if max_users is not None else 'inf'}) "
                    f"overlaps with existing tier "
                    f"({tier.min_users}-{tier.max_users if tier.max_users is not None else 'inf'})"
                ),
            )


@router.post("/internal/config/pricing/volume-tiers", status_code=201)
def create_volume_tier(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    required = ("min_users", "transactional_user_discount_pct", "limited_tech_user_discount_pct")
    for f in required:
        if body.get(f) is None:
            raise HTTPException(status_code=422, detail=f"Missing required field: {f}")
    min_u = int(body["min_users"])
    max_u = body.get("max_users")
    if max_u is not None:
        max_u = int(max_u)
    _check_tier_overlap(db, min_u, max_u)
    row = VolumeDiscountTier(
        id=uuid.uuid4(),
        min_users=min_u,
        max_users=max_u,
        transactional_user_discount_pct=body["transactional_user_discount_pct"],
        limited_tech_user_discount_pct=body["limited_tech_user_discount_pct"],
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.volume_tier_created",
        object_type="volume_discount_tier",
        object_id=row.id,
        after=_serialise_tier(row),
    )
    return _serialise_tier(row)


@router.patch("/internal/config/pricing/volume-tiers/{tier_id}")
def update_volume_tier(
    tier_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = db.query(VolumeDiscountTier).filter(VolumeDiscountTier.id == tier_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Volume tier not found")
    before = _serialise_tier(row)
    new_min = int(body["min_users"]) if "min_users" in body and body["min_users"] is not None else row.min_users
    if "max_users" in body:
        new_max = body["max_users"]
        if new_max is not None:
            new_max = int(new_max)
    else:
        new_max = row.max_users
    if new_min != row.min_users or new_max != row.max_users:
        _check_tier_overlap(db, new_min, new_max, exclude_id=row.id)
    row.min_users = new_min
    row.max_users = new_max
    if "transactional_user_discount_pct" in body and body["transactional_user_discount_pct"] is not None:
        row.transactional_user_discount_pct = body["transactional_user_discount_pct"]
    if "limited_tech_user_discount_pct" in body and body["limited_tech_user_discount_pct"] is not None:
        row.limited_tech_user_discount_pct = body["limited_tech_user_discount_pct"]
    if "is_active" in body and body["is_active"] is not None:
        row.is_active = bool(body["is_active"])
    db.commit()
    db.refresh(row)
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.volume_tier_updated",
        object_type="volume_discount_tier",
        object_id=row.id,
        before=before,
        after=_serialise_tier(row),
    )
    return _serialise_tier(row)


@router.delete("/internal/config/pricing/volume-tiers/{tier_id}")
def deactivate_volume_tier(
    tier_id: uuid.UUID,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_system_admin(current_user)
    row = db.query(VolumeDiscountTier).filter(VolumeDiscountTier.id == tier_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Volume tier not found")
    if row.is_active and not force:
        # Gap-detection: build the active list excluding this row, then check
        # whether the contiguous coverage starting at min(1) is intact.
        remaining = (
            db.query(VolumeDiscountTier)
            .filter(VolumeDiscountTier.is_active.is_(True))
            .filter(VolumeDiscountTier.id != row.id)
            .order_by(VolumeDiscountTier.min_users)
            .all()
        )
        gap = False
        if not remaining:
            gap = True
        else:
            expected = remaining[0].min_users
            for r in remaining:
                if r.min_users != expected:
                    gap = True
                    break
                if r.max_users is None:
                    expected = None
                    break
                expected = r.max_users + 1
        if gap:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Deactivating this tier would leave a gap in user band coverage. "
                    "Pass ?force=true to deactivate anyway."
                ),
            )
    row.is_active = False
    db.commit()
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.volume_tier_deactivated",
        object_type="volume_discount_tier",
        object_id=row.id,
    )
    return {"id": str(row.id), "is_active": False}


# ============================================================
# Add-on catalogue endpoints
# ============================================================


@router.post("/internal/config/pricing/addons", status_code=201)
def create_addon(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    addon_key = (body.get("addon_key") or "").lower().strip()
    if not addon_key:
        raise HTTPException(status_code=422, detail="addon_key is required")
    if not body.get("display_name"):
        raise HTTPException(status_code=422, detail="display_name is required")
    if body.get("monthly_price") in (None, ""):
        raise HTTPException(status_code=422, detail="monthly_price is required")
    existing = (
        db.query(AddonCatalogItem)
        .filter(func.lower(AddonCatalogItem.addon_key) == addon_key)
        .first()
    )
    if existing:
        raise HTTPException(status_code=422, detail=f"addon_key '{addon_key}' already exists")
    row = AddonCatalogItem(
        id=uuid.uuid4(),
        addon_key=addon_key,
        display_name=body["display_name"],
        monthly_price=body["monthly_price"],
        available_starter=bool(body.get("available_starter", False)),
        available_professional=bool(body.get("available_professional", False)),
        included_enterprise=True,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.addon_created",
        object_type="addon_catalog_item",
        object_id=row.id,
        after=_serialise_addon(row),
    )
    return _serialise_addon(row)


@router.patch("/internal/config/pricing/addons/{addon_id}")
def update_addon(
    addon_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = db.query(AddonCatalogItem).filter(AddonCatalogItem.id == addon_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Add-on not found")
    before = _serialise_addon(row)
    if "display_name" in body and body["display_name"]:
        row.display_name = body["display_name"]
    if "monthly_price" in body and body["monthly_price"] is not None:
        row.monthly_price = body["monthly_price"]
    for flag in ("available_starter", "available_professional", "is_active"):
        if flag in body and body[flag] is not None:
            setattr(row, flag, bool(body[flag]))
    db.commit()
    db.refresh(row)
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.addon_updated",
        object_type="addon_catalog_item",
        object_id=row.id,
        before=before,
        after=_serialise_addon(row),
    )
    return _serialise_addon(row)


@router.delete("/internal/config/pricing/addons/{addon_id}")
def deactivate_addon(
    addon_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_system_admin(current_user)
    row = db.query(AddonCatalogItem).filter(AddonCatalogItem.id == addon_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Add-on not found")
    row.is_active = False
    db.commit()
    log_audit_event(
        db=db,
        actor=current_user,
        action="pricing.addon_deactivated",
        object_type="addon_catalog_item",
        object_id=row.id,
    )
    return {"id": str(row.id), "is_active": False}
