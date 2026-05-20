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
    PartnerOrganization,
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

import base64
import io
from datetime import date as _date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle

from fastapi.responses import Response

from models import PartnerOrganization as _PartnerOrg

FRACTTAL_BLUE = colors.HexColor('#1A6EBB')
FRACTTAL_LIGHT = colors.HexColor('#F5F7FA')

CURRENCY_SYMBOL = {
    "USD": "$", "EUR": "EUR ", "GBP": "GBP ",
    "AUD": "A$", "CAD": "CA$", "ZAR": "R",
    "AED": "AED ", "SAR": "SAR ", "EGP": "EGP ",
}


def _fmt(val, sym):
    try:
        f = float(val)
    except Exception:
        return "-"
    return f"{sym}{f:,.2f}"


def generate_quote_pdf(
    quote_version,
    quote,
    line_items,
    deal_name,
    customer_name,
    partner_name,
    prepared_by_name,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    story = []
    header_style = ParagraphStyle('header', fontSize=18, textColor=FRACTTAL_BLUE,
                                  spaceAfter=4, fontName='Helvetica-Bold')
    title_style = ParagraphStyle('title', fontSize=14, fontName='Helvetica-Bold', spaceAfter=2)
    sub_style = ParagraphStyle('sub', fontSize=10, textColor=colors.grey, spaceAfter=2)
    footer_style = ParagraphStyle('footer', fontSize=7, textColor=colors.grey, leading=10)

    story.append(Paragraph("FRACTTAL", header_style))
    story.append(Paragraph("Software Pricing Quotation", title_style))
    scenario_suffix = (
        f" - {quote_version.scenario_label.title()}" if quote_version.scenario_label else ""
    )
    story.append(Paragraph(
        f"Quote #{str(quote.id)[:8].upper()} | Version {quote_version.version_number}{scenario_suffix}",
        sub_style,
    ))
    story.append(Paragraph(f"Date: {_date.today().strftime('%d %B %Y')}", sub_style))
    story.append(Spacer(1, 6 * mm))

    info_data = [
        ['Customer:', customer_name or '-', 'Deal:', deal_name or '-'],
        ['Partner:', partner_name or '-', 'Prepared By:', prepared_by_name or '-'],
        ['Currency:', quote.currency_code, '', ''],
    ]
    info_table = Table(info_data, colWidths=[35 * mm, 65 * mm, 30 * mm, 40 * mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    sym = CURRENCY_SYMBOL.get(quote.currency_code, '$')
    headers = ['Description', 'Qty', 'Unit Price', 'Discount', 'Total Before', 'Total After']
    col_widths = [75 * mm, 12 * mm, 25 * mm, 18 * mm, 25 * mm, 25 * mm]
    table_data = [headers]
    for item in line_items:
        unit = _fmt(item.unit_price, sym) if float(item.unit_price) > 0 else '-'
        disc = f"{float(item.discount_pct):.0f}%" if float(item.discount_pct) > 0 else '-'
        table_data.append([
            item.description,
            str(item.quantity),
            unit,
            disc,
            _fmt(item.total_before_discount, sym),
            _fmt(item.total_after_discount, sym),
        ])
    table_data.append([
        'Annual Total', '', '', '',
        _fmt(quote_version.grand_total_before_discount, sym),
        _fmt(quote_version.grand_total_after_discount, sym),
    ])

    line_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), FRACTTAL_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, FRACTTAL_LIGHT]),
        ('BACKGROUND', (0, -1), (-1, -1), FRACTTAL_LIGHT),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, FRACTTAL_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (0, -1), 3),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(
        f"This quotation is valid for 30 days from the date of issue. "
        f"Prices are in {quote.currency_code} and are per annum unless otherwise stated. "
        f"Subject to standard Fracttal terms and conditions.",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()


# ===================== Sprint 16 PDF endpoints =====================


@router.post("/quotes/{quote_id}/versions/{version_number}/generate-pdf")
def generate_pdf_for_version(
    quote_id: uuid.UUID,
    version_number: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or regenerate) the PDF artefact for a quote version.

    Internal write roles only (channel_manager, channel_ops_admin, system_admin).
    The PDF is stored base64-encoded in ``quote_versions.pdf_artifact_data`` so
    Railway's ephemeral filesystem does not lose it on redeploy (see AD-17).
    """
    _check_write_role(current_user)
    quote = _get_quote_or_404(db, quote_id)
    version = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_number == version_number,
            QuoteVersion.is_deleted.is_(False),
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Quote version not found")

    deal = _get_deal_or_404(db, quote.deal_id)
    partner = (
        db.query(_PartnerOrg)
        .filter(_PartnerOrg.id == quote.partner_org_id)
        .first()
    )
    created_by = (
        db.query(User).filter(User.id == quote.created_by).first()
    )

    line_items = (
        db.query(QuoteLineItem)
        .filter(QuoteLineItem.quote_version_id == version.id)
        .order_by(QuoteLineItem.line_order)
        .all()
    )

    pdf_bytes = generate_quote_pdf(
        quote_version=version,
        quote=quote,
        line_items=line_items,
        deal_name=deal.deal_name,
        customer_name=deal.customer_name,
        partner_name=partner.legal_name if partner else None,
        prepared_by_name=created_by.email if created_by else None,
    )
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    filename = (
        f"quote-{str(quote.id)[:8]}-v{version_number}-"
        f"{_date.today().isoformat()}.pdf"
    )

    version.pdf_artifact_data = pdf_b64
    version.pdf_generated_at = datetime.utcnow()
    version.pdf_filename = filename
    db.commit()
    db.refresh(version)

    log_audit_event(
        db=db, actor=current_user,
        action="quote.pdf_generated",
        object_type="quote",
        object_id=quote.id,
        after={"version_number": version_number, "filename": filename},
        ip_address=_client_ip(request) if request else None,
    )
    return {
        "pdf_filename": filename,
        "pdf_generated_at": version.pdf_generated_at.isoformat(),
    }


@router.get("/quotes/{quote_id}/versions/{version_number}/pdf")
def download_quote_pdf(
    quote_id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Decode and stream back the previously-generated PDF.

    Partner-side users may download their own org's quotes only; internal
    review roles may download any.
    """
    quote = _get_quote_or_404(db, quote_id)
    _check_tenant_read(current_user, quote.partner_org_id)
    version = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.version_number == version_number,
            QuoteVersion.is_deleted.is_(False),
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Quote version not found")
    if not version.pdf_artifact_data:
        raise HTTPException(
            status_code=404,
            detail="PDF has not been generated yet - call generate-pdf first",
        )
    pdf_bytes = base64.b64decode(version.pdf_artifact_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{version.pdf_filename or "quote.pdf"}"'
            )
        },
    )


# ===================== Sprint 18 — Scenario management =====================


@router.patch("/quotes/{quote_id}/active-scenario")
def set_active_scenario(
    quote_id: uuid.UUID,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-point ``quotes.active_scenario`` to a scenario label that has an
    existing (non-deleted) QuoteVersion. ``scenario_label=None`` clears it.

    Internal write roles only.
    """
    _check_write_role(current_user)
    quote = _get_quote_or_404(db, quote_id)

    scenario_label = payload.get("scenario_label")
    if scenario_label is not None and not isinstance(scenario_label, str):
        raise HTTPException(status_code=422, detail="scenario_label must be a string or null")

    if scenario_label is not None:
        match = (
            db.query(QuoteVersion)
            .filter(
                QuoteVersion.quote_id == quote.id,
                QuoteVersion.scenario_label == scenario_label,
                QuoteVersion.is_deleted.is_(False),
            )
            .first()
        )
        if match is None:
            raise HTTPException(
                status_code=422,
                detail=f"No active version with scenario_label '{scenario_label}' exists for this quote",
            )

    before = quote.active_scenario
    quote.active_scenario = scenario_label
    quote.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(quote)

    log_audit_event(
        db=db,
        actor=current_user,
        action="quote.scenario_selected",
        object_type="quote",
        object_id=quote.id,
        before={"active_scenario": before},
        after={"active_scenario": scenario_label},
        ip_address=_client_ip(request) if request else None,
    )
    return _serialize_quote(quote)


@router.get("/quotes/{quote_id}/scenarios")
def get_quote_scenarios(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return one entry per scenario_label (good/better/best) — latest non-deleted
    version per label. ``is_active=True`` flags the label that matches
    ``quote.active_scenario``. Always returns in canonical good/better/best order.
    """
    quote = _get_quote_or_404(db, quote_id)
    _check_tenant_read(current_user, quote.partner_org_id)

    versions = (
        db.query(QuoteVersion)
        .filter(
            QuoteVersion.quote_id == quote.id,
            QuoteVersion.scenario_label.isnot(None),
            QuoteVersion.is_deleted.is_(False),
        )
        .order_by(QuoteVersion.version_number.desc())
        .all()
    )

    latest_by_label: dict[str, QuoteVersion] = {}
    for v in versions:
        if v.scenario_label not in latest_by_label:
            latest_by_label[v.scenario_label] = v

    canonical_order = ["good", "better", "best"]
    extras = [label for label in latest_by_label if label not in canonical_order]
    order = canonical_order + sorted(extras)

    scenarios = []
    for label in order:
        v = latest_by_label.get(label)
        if v is None:
            continue
        scenarios.append({
            "scenario_label": label,
            "version_number": v.version_number,
            "feature_plan": v.feature_plan,
            "grand_total_after_discount": float(v.grand_total_after_discount),
            "is_active": quote.active_scenario == label,
        })

    return {"scenarios": scenarios, "active_scenario": quote.active_scenario}


# ===================== Sprint 18 — Internal quote dashboard =====================


@router.get("/internal/quotes")
def list_internal_quotes(
    status: Optional[str] = None,
    partner_org_id: Optional[uuid.UUID] = None,
    feature_plan: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cross-deal quote dashboard for internal review/ops roles."""
    if UserRole(current_user.role) not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    elif page_size > 100:
        page_size = 100

    base = (
        db.query(Quote, QuoteVersion, DealRegistration, PartnerOrganization)
        .join(
            QuoteVersion,
            and_(
                QuoteVersion.quote_id == Quote.id,
                QuoteVersion.version_number == Quote.active_version,
                QuoteVersion.is_deleted.is_(False),
            ),
        )
        .join(DealRegistration, DealRegistration.id == Quote.deal_id)
        .join(PartnerOrganization, PartnerOrganization.id == Quote.partner_org_id)
    )
    if status:
        base = base.filter(Quote.status == status)
    if partner_org_id:
        base = base.filter(Quote.partner_org_id == partner_org_id)
    if feature_plan:
        base = base.filter(QuoteVersion.feature_plan == feature_plan)
    if search:
        like = f"%{search}%"
        base = base.filter(or_(Quote.quote_name.ilike(like), DealRegistration.deal_name.ilike(like)))

    total = base.count()
    rows = (
        base.order_by(Quote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for quote, version, deal, partner in rows:
        items.append(
            {
                "id": str(quote.id),
                "quote_name": quote.quote_name or "Untitled Quote",
                "deal_id": str(quote.deal_id),
                "deal_name": deal.deal_name or "—",
                "partner_org_id": str(quote.partner_org_id),
                "partner_org_name": partner.legal_name,
                "currency_code": quote.currency_code,
                "feature_plan": version.feature_plan,
                "active_version": quote.active_version,
                "active_scenario": quote.active_scenario,
                "grand_total_after_discount": float(version.grand_total_after_discount),
                "status": quote.status,
                "created_at": quote.created_at.isoformat() if quote.created_at else None,
            }
        )

    # Summary across all quotes (not filtered) — small enough at current volumes
    all_quotes = db.query(Quote).all()
    pipeline_total = 0.0
    for q in all_quotes:
        if q.status == "expired":
            continue
        av = (
            db.query(QuoteVersion)
            .filter(
                QuoteVersion.quote_id == q.id,
                QuoteVersion.version_number == q.active_version,
                QuoteVersion.is_deleted.is_(False),
            )
            .first()
        )
        if av is None:
            continue
        pipeline_total += float(av.grand_total_after_discount or 0)

    summary = {
        "total_quotes": len(all_quotes),
        "draft": sum(1 for q in all_quotes if q.status == "draft"),
        "sent": sum(1 for q in all_quotes if q.status == "sent"),
        "accepted": sum(1 for q in all_quotes if q.status == "accepted"),
        "expired": sum(1 for q in all_quotes if q.status == "expired"),
        "pipeline_total": round(pipeline_total, 2),
    }

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
    }

