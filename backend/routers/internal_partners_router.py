"""Sprint 12 / FPRM-205 — internal-admin cross-org partner list.

Searchable, filterable list of all partner organisations. Backs the
`/internal/partners` page introduced in Sprint 12 (the nav item was added
in Sprint 11's InternalLayout and stayed disabled until this story).

Route:
    GET /internal/partners  — channel_manager / channel_ops_admin / system_admin
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user
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
