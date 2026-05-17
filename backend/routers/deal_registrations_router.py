"""Deal registration endpoints (Sprint 8 / FPRM-128).

Partner-facing endpoints:
    POST   /deal-registrations              partner_admin — create draft (activation-gated)
    GET    /deal-registrations              tenant-scoped — list deals
    GET    /deal-registrations/{id}         tenant-scoped — get one
    PATCH  /deal-registrations/{id}         partner_admin own + draft only — update
    POST   /deal-registrations/{id}/submit  partner_admin own — draft -> submitted, snapshot commission
    DELETE /deal-registrations/{id}         partner_admin own + draft only — delete draft

Activation gate: ``POST /deal-registrations`` requires
``partner_activation_checklists.activation_complete = True`` for the submitter's
org; otherwise returns 412 with `{detail, activation_url}`. The gate runs on
create only — drafts are allowed once a partner is fully active. Subsequent
submit/patch/delete operations are not re-gated.

Commission snapshot (on submit): resolves a row from ``commission_structures``
keyed by ``(partner_category_code, commission_type, year_1)`` and stores the id
+ percentage on the deal. If no row matches the deal's commission_type, the
snapshot fields stay null (the form's commission_type vocabulary is broader
than the commission_structures enum by design — Sprint 10's commission
visibility story will surface this to partners). See AD-14 for activation
recalc isolation — deal submission does not trigger activation recalc.

The internal review queue endpoints (`/internal/deals/*`) are added in
Story 5 / FPRM-134 in this same file.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import (
    CommissionStructure,
    CommissionYear,
    DealRegistration,
    PartnerActivationChecklist,
    PartnerOrganization,
    User,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole


router = APIRouter(tags=["deal-registrations"])


CREATABLE_FIELDS = {
    "customer_name", "customer_domain", "customer_contact_name",
    "customer_contact_email", "customer_contact_phone", "customer_industry",
    "customer_country", "customer_region",
    "deal_name", "estimated_deal_value", "estimated_close_date",
    "deal_notes", "commission_type",
}


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _serialize(deal: DealRegistration) -> dict:
    return jsonable_encoder({c.name: getattr(deal, c.name) for c in deal.__table__.columns})


def _require_partner_admin(user: User) -> None:
    if UserRole(user.role) != UserRole.partner_admin:
        raise HTTPException(
            status_code=403,
            detail="Only partner_admin can perform this action",
        )
    if user.partner_org_id is None:
        raise HTTPException(
            status_code=403,
            detail="Partner admin is not linked to an organisation",
        )


def _enforce_tenant_read(user: User, deal: DealRegistration) -> None:
    role = UserRole(user.role)
    if role in PARTNER_ROLES:
        if user.partner_org_id is None or str(user.partner_org_id) != str(deal.partner_org_id):
            raise HTTPException(status_code=403, detail="Access denied")


def _get_deal_or_404(deal_id: uuid.UUID, db: Session) -> DealRegistration:
    deal = db.query(DealRegistration).filter(DealRegistration.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal registration not found")
    return deal


def _check_activation(db: Session, partner_org_id: uuid.UUID) -> None:
    """Activation gate per AD-14: deal create requires activation_complete=True.

    A missing checklist row is treated as not-activated. We do NOT call
    ``recalculate_activation`` here — deal-registration is downstream of
    activation, never upstream (AD-14 keeps recalc inside activation.py only).
    """
    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_org_id)
        .first()
    )
    if not checklist or not checklist.activation_complete:
        raise HTTPException(
            status_code=412,
            detail={
                "detail": "Partner activation incomplete",
                "activation_url": "/portal/home",
            },
        )


def _snapshot_commission(db: Session, deal: DealRegistration) -> None:
    """Resolve commission_structures row matching the deal + partner category.

    Best-effort: if the partner_organization is missing, or no matching row
    exists for the (partner_category_code, commission_type, year_1) tuple,
    leave commission_structure_id and commission_rate_snapshot as None. Never
    raise — a missing snapshot is acceptable and surfaces in the internal
    review queue as a blank commission.
    """
    if not deal.commission_type:
        return

    org = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == deal.partner_org_id)
        .first()
    )
    if org is None or org.partner_category is None:
        return
    code = org.partner_category.value if hasattr(org.partner_category, "value") else str(org.partner_category)

    row = (
        db.query(CommissionStructure)
        .filter(
            CommissionStructure.partner_category_code == code,
            CommissionStructure.commission_type == deal.commission_type,
            CommissionStructure.year == CommissionYear.year_1,
        )
        .first()
    )
    if row is None:
        return
    deal.commission_structure_id = row.id
    try:
        deal.commission_rate_snapshot = float(row.commission_pct)
    except (TypeError, ValueError):
        deal.commission_rate_snapshot = None


@router.post("/deal-registrations", status_code=201)
def create_deal(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new draft deal registration. partner_admin role only; activation gated."""
    _require_partner_admin(current_user)
    _check_activation(db, current_user.partner_org_id)

    if not (payload.get("customer_name") or "").strip():
        raise HTTPException(status_code=422, detail="customer_name is required")
    if not (payload.get("deal_name") or "").strip():
        raise HTTPException(status_code=422, detail="deal_name is required")

    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=current_user.partner_org_id,
        status="draft",
        conflict_status="not_checked",
    )
    for key, value in payload.items():
        if key in CREATABLE_FIELDS:
            setattr(deal, key, value)
    db.add(deal)
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.created",
        object_type="deal_registration",
        object_id=deal.id,
        after={"status": deal.status, "deal_name": deal.deal_name},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.get("/deal-registrations")
def list_deals(
    status: Optional[str] = Query(default=None),
    partner_org_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List deals. partner roles see own org only; internal roles see all (filterable)."""
    role = UserRole(current_user.role)
    query = db.query(DealRegistration)

    if role in PARTNER_ROLES:
        if current_user.partner_org_id is None:
            return {"total": 0, "limit": limit, "offset": offset, "items": []}
        query = query.filter(DealRegistration.partner_org_id == current_user.partner_org_id)
    elif role in INTERNAL_ROLES:
        if partner_org_id is not None:
            query = query.filter(DealRegistration.partner_org_id == partner_org_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    if status:
        query = query.filter(DealRegistration.status == status)

    total = query.count()
    items = (
        query.order_by(DealRegistration.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize(d) for d in items],
    }


@router.get("/deal-registrations/{deal_id}")
def get_deal(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = _get_deal_or_404(deal_id, db)
    _enforce_tenant_read(current_user, deal)
    return _serialize(deal)


@router.patch("/deal-registrations/{deal_id}")
def update_deal(
    deal_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update draft fields. partner_admin own org only; draft status only."""
    _require_partner_admin(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if str(deal.partner_org_id) != str(current_user.partner_org_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if deal.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit deal in status '{deal.status}'",
        )

    before = _serialize(deal)
    for key, value in payload.items():
        if key in CREATABLE_FIELDS:
            setattr(deal, key, value)
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.updated",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before["status"]},
        after={"status": deal.status},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.post("/deal-registrations/{deal_id}/submit")
def submit_deal(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a draft (or info_required) deal. Snapshots commission rate."""
    _require_partner_admin(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if str(deal.partner_org_id) != str(current_user.partner_org_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if deal.status not in ("draft", "info_required"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit deal in status '{deal.status}'",
        )
    if not (deal.customer_name or "").strip() or not (deal.deal_name or "").strip():
        raise HTTPException(
            status_code=422,
            detail="customer_name and deal_name are required to submit",
        )

    before_status = deal.status
    _snapshot_commission(db, deal)
    deal.status = "submitted"
    deal.submitted_at = datetime.utcnow()
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.submitted",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={
            "status": "submitted",
            "commission_structure_id": str(deal.commission_structure_id) if deal.commission_structure_id else None,
            "commission_rate_snapshot": deal.commission_rate_snapshot,
        },
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.delete("/deal-registrations/{deal_id}", status_code=204)
def delete_deal(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a draft. partner_admin own org only; draft status only."""
    _require_partner_admin(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if str(deal.partner_org_id) != str(current_user.partner_org_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if deal.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete deal in status '{deal.status}'",
        )

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.deleted",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": "draft", "deal_name": deal.deal_name},
        ip_address=_client_ip(request),
    )
    db.delete(deal)
    db.commit()
    return None
