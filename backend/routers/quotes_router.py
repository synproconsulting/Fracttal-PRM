"""Sprint 15 / FPRM-246 — Quote CRUD API.

Wraps :func:`quote_engine.calculate_quote` (AD-16: single source of truth for
pricing) and persists results to ``quotes`` / ``quote_versions`` /
``quote_line_items``.

Endpoints
---------

Partner-side (tenant scoped to own org):

    POST   /deals/{deal_id}/quotes                Create a new quote (partner_admin own deal + internal review roles)
    GET    /deals/{deal_id}/quotes                List quotes for a deal
    GET    /quotes/{quote_id}                     Read quote + active-version data
    GET    /quotes/{quote_id}/versions            List all versions (incl. soft-deleted)

Internal-only (write-side):

    POST   /quotes/{quote_id}/versions            Add a new version
    PATCH  /quotes/{quote_id}/active-version      Re-point the active version
    PATCH  /quotes/{quote_id}/status              draft -> sent | sent -> accepted | sent -> expired
    DELETE /quotes/{quote_id}/versions/{version}  Soft-delete a non-active version

Pricing catalogue (any authenticated user, needed by the quote form UI):

    GET    /internal/config/pricing/plans         Active FeaturePlanPrice rows
    GET    /internal/config/pricing/addons        Active AddonCatalogItem rows
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user
from database import get_db
from models import (
    AddonCatalogItem,
    DealRegistration,
    FeaturePlanPrice,
    Quote,
    QuoteLineItem,
    QuoteVersion,
    User,
)
from quote_engine import calculate_quote
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole


router = APIRouter(tags=["quotes"])


WRITE_ROLES = {
    UserRole.channel_manager,
    UserRole.channel_ops_admin,
    UserRole.system_admin,
}
DELETE_ROLES = {UserRole.channel_ops_admin, UserRole.system_admin}
ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"sent"},
    "sent": {"accepted", "expired"},
}


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _serialize_line_item(line: QuoteLineItem) -> dict:
    return jsonable_encoder(
        {c.name: getattr(line, c.name) for c in line.__table__.columns}
    )


def _serialize_version(
    version: QuoteVersion, line_items: Optional[list[QuoteLineItem]] = None
) -> dict:
    body = jsonable_encoder(
        {c.name: getattr(version, c.name) for c in version.__table__.columns}
    )
    if line_items is not None:
        body["line_items"] = [
            _serialize_line_item(li)
            for li in sorted(line_items, key=lambda x: x.line_order)
        ]
    return body


def _serialize_quote(quote: Quote, active_version_data: Optional[dict] = None) -> dict:
    body = jsonable_encoder(
        {c.name: getattr(quote, c.name) for c in quote.__table__.columns}
    )
    if active_version_data is not None:
        body["active_version_data"] = active_version_data
    return body


def _get_deal_or_404(db: Session, deal_id: uuid.UUID) -> DealRegistration:
    deal = db.query(DealRegistration).filter(DealRegistration.id == deal_id).first()
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal registration not found")
    return deal


def _get_quote_or_404(db: Session, quote_id: uuid.UUID) -> Quote:
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


def _check_tenant_read(user: User, partner_org_id: uuid.UUID) -> None:
    """Partner-side users can only access their own org's quotes."""
    role = UserRole(user.role)
    if role in PARTNER_ROLES:
        if user.partner_org_id is None or str(user.partner_org_id) != str(partner_org_id):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")


def _check_write_role(user: User) -> None:
    if UserRole(user.role) not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Permission denied: write role required")


def _persist_version(
    db: Session,
    quote: Quote,
    version_number: int,
    scenario_label: Optional[str],
    feature_plan: str,
    feature_plan_discount_pct: float,
    qty_transactional_users: int,
    qty_limited_tech_users: int,
    selected_addon_keys: list[str],
) -> tuple[QuoteVersion, list[QuoteLineItem]]:
    """Run the engine and persist a QuoteVersion + its QuoteLineItem rows.

    Engine ValueErrors are converted to HTTP 422 here so callers don't need to.
    """
    try:
        result = calculate_quote(
            db=db,
            feature_plan=feature_plan,
            feature_plan_discount_pct=feature_plan_discount_pct,
            qty_transactional=qty_transactional_users,
            qty_limited_tech_quoted=qty_limited_tech_users,
            selected_addon_keys=list(selected_addon_keys or []),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    version = QuoteVersion(
        id=uuid.uuid4(),
        quote_id=quote.id,
        version_number=version_number,
        scenario_label=scenario_label,
        feature_plan=feature_plan,
        feature_plan_discount_pct=Decimal(str(feature_plan_discount_pct)),
        qty_transactional_users=qty_transactional_users,
        qty_limited_tech_users=qty_limited_tech_users,
        selected_addons=list(selected_addon_keys or []),
        grand_total_before_discount=result.grand_total_before_discount,
        grand_total_after_discount=result.grand_total_after_discount,
    )
    db.add(version)
    db.flush()

    lines: list[QuoteLineItem] = []
    for line in result.line_items:
        row = QuoteLineItem(
            id=uuid.uuid4(),
            quote_version_id=version.id,
            line_order=line.line_order,
            line_type=line.line_type,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_pct=line.discount_pct,
            total_before_discount=line.total_before_discount,
            total_after_discount=line.total_after_discount,
            addon_key=line.addon_key,
        )
        db.add(row)
        lines.append(row)
    db.commit()
    db.refresh(version)
    for li in lines:
        db.refresh(li)
    return version, lines


# ===================== Pricing catalogue read endpoints =====================


@router.get("/internal/config/pricing/plans")
def list_pricing_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active FeaturePlanPrice rows. Any authenticated user (needed by the
    quote form UI to display current prices)."""
    rows = (
        db.query(FeaturePlanPrice)
        .filter(FeaturePlanPrice.is_active.is_(True))
        .order_by(FeaturePlanPrice.plan_code)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "plan_code": r.plan_code,
            "feature_pack_annual": str(r.feature_pack_annual),
            "transactional_user_annual": str(r.transactional_user_annual),
            "limited_tech_user_annual": str(r.limited_tech_user_annual),
            "effective_from": r.effective_from.isoformat(),
        }
        for r in rows
    ]


@router.get("/internal/config/pricing/addons")
def list_addon_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active AddonCatalogItem rows."""
    rows = (
        db.query(AddonCatalogItem)
        .filter(AddonCatalogItem.is_active.is_(True))
        .order_by(AddonCatalogItem.display_name)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "addon_key": r.addon_key,
            "display_name": r.display_name,
            "monthly_price": str(r.monthly_price),
            "available_starter": r.available_starter,
            "available_professional": r.available_professional,
            "included_enterprise": r.included_enterprise,
        }
        for r in rows
    ]


# ===================== Create / list / read quotes =====================


@router.post("/deals/{deal_id}/quotes", status_code=201)
def create_quote_for_deal(
    deal_id: uuid.UUID,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Quote with version 1 for a deal.

    Roles: partner_admin (own deal) + channel_manager + channel_ops_admin +
    system_admin. Validation: deal exists; partner_admin can only quote on
    their own org's deals; deal must not be ``rejected`` / ``cancelled``.
    """
    deal = _get_deal_or_404(db, deal_id)

    role = UserRole(current_user.role)
    if role == UserRole.partner_admin:
        if (
            current_user.partner_org_id is None
            or str(current_user.partner_org_id) != str(deal.partner_org_id)
        ):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Permission denied")

    if deal.status in ("rejected", "cancelled"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot create quote for deal in status '{deal.status}'",
        )

    feature_plan = payload.get("feature_plan")
    if not feature_plan:
        raise HTTPException(status_code=422, detail="feature_plan is required")
    if payload.get("qty_transactional_users") is None:
        raise HTTPException(status_code=422, detail="qty_transactional_users is required")
    if payload.get("qty_limited_tech_users") is None:
        raise HTTPException(status_code=422, detail="qty_limited_tech_users is required")

    quote = Quote(
        id=uuid.uuid4(),
        deal_id=deal.id,
        partner_org_id=deal.partner_org_id,
        created_by=current_user.id,
        quote_name=payload.get("quote_name"),
        currency_code=payload.get("currency_code") or "USD",
        active_version=1,
        active_scenario=payload.get("scenario_label"),
        status="draft",
    )
    db.add(quote)
    db.flush()

    version, lines = _persist_version(
        db=db, quote=quote, version_number=1,
        scenario_label=payload.get("scenario_label"),
        feature_plan=feature_plan,
        feature_plan_discount_pct=float(payload.get("feature_plan_discount_pct") or 0),
        qty_transactional_users=int(payload["qty_transactional_users"]),
        qty_limited_tech_users=int(payload["qty_limited_tech_users"]),
        selected_addon_keys=payload.get("selected_addon_keys") or [],
    )

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.created",
        object_type="quote",
        object_id=quote.id,
        after={
            "deal_id": str(deal.id),
            "feature_plan": feature_plan,
            "version_number": 1,
        },
        ip_address=_client_ip(request) if request else None,
    )
    return _serialize_quote(quote, _serialize_version(version, lines))


@router.get("/deals/{deal_id}/quotes")
def list_quotes_for_deal(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all quotes for a deal. Partner roles see own-org only."""
    deal = _get_deal_or_404(db, deal_id)
    _check_tenant_read(current_user, deal.partner_org_id)

    quotes = (
        db.query(Quote)
        .filter(Quote.deal_id == deal.id)
        .order_by(Quote.created_at.desc())
        .all()
    )
    items = []
    for q in quotes:
        active = (
            db.query(QuoteVersion)
            .filter(
                QuoteVersion.quote_id == q.id,
                QuoteVersion.version_number == q.active_version,
                QuoteVersion.is_deleted.is_(False),
            )
            .first()
        )
        items.append(
            {
                "id": str(q.id),
                "quote_name": q.quote_name,
                "currency_code": q.currency_code,
                "active_version": q.active_version,
                "active_scenario": q.active_scenario,
                "status": q.status,
                "created_at": q.created_at.isoformat() if q.created_at else None,
                "grand_total_after_discount": (
                    str(active.grand_total_after_discount) if active else None
                ),
            }
        )
    return items


@router.get("/quotes/{quote_id}")
def get_quote(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full quote: header + active_version_data with ordered line items."""
    quote = _get_quote_or_404(db, quote_id)
    _check_tenant_read(current_user, quote.partner_org_id)
    active = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_number == quote.active_version,
        )
        .first()
    )
    active_payload = None
    if active is not None:
        lines = (
            db.query(QuoteLineItem)
            .filter(QuoteLineItem.quote_version_id == active.id)
            .all()
        )
        active_payload = _serialize_version(active, lines)
    return _serialize_quote(quote, active_payload)


# ===================== Version management =====================


@router.post("/quotes/{quote_id}/versions", status_code=201)
def add_quote_version(
    quote_id: uuid.UUID,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new version to an existing quote. Internal write roles only.

    ``active_version`` is NOT changed automatically — caller must explicitly
    set it via ``PATCH /quotes/{id}/active-version`` to re-point.
    """
    _check_write_role(current_user)
    quote = _get_quote_or_404(db, quote_id)

    if not payload.get("feature_plan"):
        raise HTTPException(status_code=422, detail="feature_plan is required")
    if payload.get("qty_transactional_users") is None:
        raise HTTPException(status_code=422, detail="qty_transactional_users is required")
    if payload.get("qty_limited_tech_users") is None:
        raise HTTPException(status_code=422, detail="qty_limited_tech_users is required")

    existing_max = (
        db.query(QuoteVersion)
        .filter(QuoteVersion.quote_id == quote.id)
        .order_by(QuoteVersion.version_number.desc())
        .first()
    )
    new_version_number = (existing_max.version_number if existing_max else 0) + 1

    version, lines = _persist_version(
        db=db, quote=quote, version_number=new_version_number,
        scenario_label=payload.get("scenario_label"),
        feature_plan=payload["feature_plan"],
        feature_plan_discount_pct=float(payload.get("feature_plan_discount_pct") or 0),
        qty_transactional_users=int(payload["qty_transactional_users"]),
        qty_limited_tech_users=int(payload["qty_limited_tech_users"]),
        selected_addon_keys=payload.get("selected_addon_keys") or [],
    )

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.version_added",
        object_type="quote",
        object_id=quote.id,
        after={"version_number": new_version_number, "feature_plan": payload["feature_plan"]},
        ip_address=_client_ip(request) if request else None,
    )
    return _serialize_version(version, lines)


@router.patch("/quotes/{quote_id}/active-version")
def set_active_version(
    quote_id: uuid.UUID,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-point ``quotes.active_version``. Internal write roles only."""
    _check_write_role(current_user)
    quote = _get_quote_or_404(db, quote_id)

    target = payload.get("version_number")
    if target is None:
        raise HTTPException(status_code=422, detail="version_number is required")
    target = int(target)

    target_version = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_number == target,
            QuoteVersion.is_deleted.is_(False),
        )
        .first()
    )
    if target_version is None:
        raise HTTPException(
            status_code=422,
            detail=f"Quote has no active version {target} (or it is soft-deleted)",
        )

    before = quote.active_version
    quote.active_version = target
    if "scenario_label" in payload:
        quote.active_scenario = payload["scenario_label"]
    quote.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(quote)

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.version_activated",
        object_type="quote",
        object_id=quote.id,
        before={"active_version": before},
        after={"active_version": target, "active_scenario": quote.active_scenario},
        ip_address=_client_ip(request) if request else None,
    )
    return _serialize_quote(quote)


@router.patch("/quotes/{quote_id}/status")
def update_quote_status(
    quote_id: uuid.UUID,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Status transitions: draft -> sent | sent -> accepted | sent -> expired."""
    _check_write_role(current_user)
    quote = _get_quote_or_404(db, quote_id)
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=422, detail="status is required")

    allowed = ALLOWED_STATUS_TRANSITIONS.get(quote.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status transition: {quote.status} -> {new_status}",
        )

    before = quote.status
    quote.status = new_status
    quote.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(quote)

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.status_changed",
        object_type="quote",
        object_id=quote.id,
        before={"status": before},
        after={"status": new_status},
        ip_address=_client_ip(request) if request else None,
    )
    return _serialize_quote(quote)


@router.get("/quotes/{quote_id}/versions")
def list_quote_versions(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All versions for a quote (incl. soft-deleted, marked with is_deleted)."""
    quote = _get_quote_or_404(db, quote_id)
    _check_tenant_read(current_user, quote.partner_org_id)
    versions = (
        db.query(QuoteVersion)
        .filter(QuoteVersion.quote_id == quote.id)
        .order_by(QuoteVersion.version_number.asc())
        .all()
    )
    return [
        {
            "version_number": v.version_number,
            "scenario_label": v.scenario_label,
            "feature_plan": v.feature_plan,
            "grand_total_after_discount": str(v.grand_total_after_discount),
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "is_deleted": v.is_deleted,
        }
        for v in versions
    ]


@router.delete("/quotes/{quote_id}/versions/{version_number}")
def soft_delete_version(
    quote_id: uuid.UUID,
    version_number: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a version. system_admin + channel_ops_admin only. Cannot
    delete the currently active version."""
    if UserRole(current_user.role) not in DELETE_ROLES:
        raise HTTPException(status_code=403, detail="Permission denied: delete role required")
    quote = _get_quote_or_404(db, quote_id)
    if version_number == quote.active_version:
        raise HTTPException(
            status_code=422,
            detail="Cannot delete the currently active version",
        )
    version = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_number == version_number,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Quote version not found")
    if version.is_deleted:
        return {"version_number": version_number, "is_deleted": True}
    version.is_deleted = True
    db.commit()

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.version_deleted",
        object_type="quote",
        object_id=quote.id,
        after={"version_number": version_number},
        ip_address=_client_ip(request) if request else None,
    )
    return {"version_number": version_number, "is_deleted": True}
