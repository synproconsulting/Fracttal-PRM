"""Sprint 12 / FPRM-205 + Sprint 13 / FPRM-208 — internal-admin partner endpoints.

Searchable, filterable list of all partner organisations plus admin-only
lifecycle controls.

Routes:
    GET   /internal/partners              — channel_manager / channel_ops_admin / system_admin
    PATCH /internal/partners/{id}/status  — channel_ops_admin / system_admin only (FPRM-208)
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user
from csv_export import csv_response
from database import get_db
from models import (
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerOrganization,
    PartnerStatus,
    PartnerTier,
    User,
)
from roles import UserRole


router = APIRouter(prefix="/internal/partners", tags=["internal-partners"])


LIST_ROLES = {
    UserRole.system_admin,
    UserRole.channel_ops_admin,
    UserRole.channel_manager,
}


def require_partner_list_role(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role not in LIST_ROLES:
        raise HTTPException(
            status_code=403,
            detail="channel_manager / channel_ops_admin / system_admin required",
        )
    return current_user


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


@router.get("")
def list_partners_for_internal(
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    export: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_partner_list_role),
):
    # Validate filter enum values defensively so the user gets a 422 with a
    # clear message instead of a 500 from the dialect cast.
    if status is not None and status not in {s.value for s in PartnerStatus}:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(s.value for s in PartnerStatus)}",
        )
    if tier is not None and tier not in {t.value for t in PartnerTier}:
        raise HTTPException(
            status_code=422,
            detail=f"tier must be one of {sorted(t.value for t in PartnerTier)}",
        )
    if category is not None and category not in {c.value for c in PartnerCategory}:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of {sorted(c.value for c in PartnerCategory)}",
        )

    query = db.query(PartnerOrganization)
    if search:
        like = f"%{search.lower()}%"
        # Use a portable lower() comparison so SQLite and Postgres both work.
        from sqlalchemy import func
        query = query.filter(func.lower(PartnerOrganization.legal_name).like(like))
    if status:
        query = query.filter(PartnerOrganization.status == status)
    if tier:
        query = query.filter(PartnerOrganization.tier == tier)
    if category:
        query = query.filter(PartnerOrganization.partner_category == category)

    if export == "csv":
        csv_rows = query.order_by(PartnerOrganization.created_at.desc()).all()
        csv_org_ids = [p.id for p in csv_rows]
        csv_activation: dict = {}
        if csv_org_ids:
            for c in db.query(PartnerActivationChecklist).filter(PartnerActivationChecklist.partner_org_id.in_(csv_org_ids)).all():
                csv_activation[c.partner_org_id] = bool(c.activation_complete)
        return csv_response(
            "partners_export",
            ["Legal Name", "Program Type", "Category", "Tier", "Status",
             "Activation Complete", "Created Date"],
            [
                [
                    p.legal_name or "",
                    _enum_value(p.program_type),
                    _enum_value(p.partner_category),
                    _enum_value(p.tier) if p.tier is not None else "",
                    _enum_value(p.status),
                    "Yes" if csv_activation.get(p.id, False) else "No",
                    p.created_at.date().isoformat() if p.created_at else "",
                ]
                for p in csv_rows
            ],
        )

    total = query.count()
    rows = (
        query.order_by(PartnerOrganization.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    org_ids = [p.id for p in rows]
    activation_map: dict = {}
    if org_ids:
        checklists = (
            db.query(PartnerActivationChecklist)
            .filter(PartnerActivationChecklist.partner_org_id.in_(org_ids))
            .all()
        )
        activation_map = {c.partner_org_id: bool(c.activation_complete) for c in checklists}

    items = []
    for p in rows:
        items.append({
            "id": str(p.id),
            "legal_name": p.legal_name,
            "program_type": _enum_value(p.program_type),
            "partner_category": _enum_value(p.partner_category),
            "tier": _enum_value(p.tier) if p.tier is not None else None,
            "status": _enum_value(p.status),
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "activation_complete": activation_map.get(p.id, False),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---- FPRM-208 — partner organisation status management --------------------


STATUS_ADMIN_ROLES = {
    UserRole.system_admin,
    UserRole.channel_ops_admin,
}

# Statuses internal admins are allowed to set via this endpoint. ``applicant``
# is intentionally excluded — it is only ever set by the partner-application
# approval flow that mints the org.
ALLOWED_STATUS_VALUES = {"active", "suspended", "terminated", "inactive"}


def require_status_admin_role(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role not in STATUS_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="channel_ops_admin or system_admin required to change partner status",
        )
    return current_user


def _serialize_org(partner: PartnerOrganization) -> dict:
    return {c.name: getattr(partner, c.name) for c in partner.__table__.columns}


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.patch("/{partner_id}/status")
def update_partner_status(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_status_admin_role),
):
    """Set a partner organisation's lifecycle status (FPRM-208).

    Allowed transitions: ``active`` ⇄ ``suspended`` ⇄ ``terminated`` (and
    ``inactive``). ``applicant`` is rejected — that state is only set by the
    partner-application approval flow.
    """
    new_status = payload.get("status") if isinstance(payload, dict) else None
    if new_status is None:
        raise HTTPException(status_code=400, detail="status is required")
    if not isinstance(new_status, str):
        raise HTTPException(status_code=400, detail="status must be a string")
    if new_status == "applicant":
        raise HTTPException(
            status_code=400,
            detail="status 'applicant' cannot be set via this endpoint",
        )
    if new_status not in ALLOWED_STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUS_VALUES)}",
        )

    partner = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == partner_id)
        .first()
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    before = jsonable_encoder(_serialize_org(partner))
    old_status = _enum_value(partner.status)
    partner.status = new_status
    partner.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(partner)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_org.status_changed",
        object_type="partner_organization",
        object_id=partner.id,
        before=before,
        after=jsonable_encoder(_serialize_org(partner)),
        ip_address=_client_ip(request),
        notes=f"{old_status} -> {new_status}",
    )

    return _serialize_org(partner)
