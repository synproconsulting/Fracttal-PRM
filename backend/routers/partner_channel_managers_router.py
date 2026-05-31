"""Channel-manager <-> partner assignment CRUD (Sprint 24 PR B / FPRM-422 / AD-41).

Endpoints
---------
GET    /partners/{id}/channel-managers            any internal role; resolved name+email
POST   /partners/{id}/channel-managers            system_admin + channel_ops_admin; body {user_id}
DELETE /partners/{id}/channel-managers/{user_id}  system_admin + channel_ops_admin

The assigned user must hold the ``channel_manager`` role (422 otherwise). A
repeat assignment is idempotent via the unique(partner_org_id, user_id)
constraint (409). Tenant scope / role checks live in the handler per AD-9.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import PartnerChannelManager, PartnerOrganization, User
from permissions import get_all_channel_managers
from roles import INTERNAL_ROLES, UserRole

router = APIRouter(tags=["channel-manager-assignment"])

# Only these two roles may assign/unassign (hardcoded per AD-41; becomes
# RBAC-administrable when Dynamic RBAC lands in Phase 7).
_ASSIGN_ROLES = {UserRole.system_admin, UserRole.channel_ops_admin}


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def _partner_or_404(db: Session, partner_id: uuid.UUID) -> PartnerOrganization:
    p = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return p


def _serialize(row: PartnerChannelManager, user: Optional[User]) -> dict:
    return {
        "id": str(row.id),
        "partner_org_id": str(row.partner_org_id),
        "user_id": str(row.user_id),
        "full_name": (user.full_name if user else None),
        "email": (user.email if user else None),
        "assigned_by": str(row.assigned_by) if row.assigned_by else None,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
    }


@router.get("/internal/channel-managers")
def list_channel_manager_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All active channel_manager users -- the assignment picker's candidate
    list. Restricted to the roles that may assign (the picker is only shown to
    them); avoids the system_admin-only /internal/users endpoint."""
    if UserRole(current_user.role) not in _ASSIGN_ROLES:
        raise HTTPException(status_code=403, detail="Only system_admin or channel_ops_admin")
    return {
        "items": [
            {"user_id": str(u.id), "full_name": u.full_name, "email": u.email}
            for u in get_all_channel_managers(db)
        ]
    }


@router.get("/partners/{partner_id}/channel-managers")
def list_channel_managers(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the channel managers assigned to a partner. Any internal role."""
    if UserRole(current_user.role) not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")
    _partner_or_404(db, partner_id)
    rows = (
        db.query(PartnerChannelManager)
        .filter(PartnerChannelManager.partner_org_id == partner_id)
        .all()
    )
    user_ids = {r.user_id for r in rows}
    users = {
        u.id: u for u in (db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else [])
    }
    return {"items": [_serialize(r, users.get(r.user_id)) for r in rows]}


@router.post("/partners/{partner_id}/channel-managers", status_code=201)
def assign_channel_manager(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a channel manager to a partner. system_admin + channel_ops_admin only."""
    if UserRole(current_user.role) not in _ASSIGN_ROLES:
        raise HTTPException(status_code=403, detail="Only system_admin or channel_ops_admin may assign channel managers")
    _partner_or_404(db, partner_id)

    raw = payload.get("user_id")
    if not raw:
        raise HTTPException(status_code=422, detail="user_id is required")
    try:
        user_id = uuid.UUID(str(raw))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid user_id")

    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=422, detail="User not found")
    if UserRole(target.role) != UserRole.channel_manager:
        raise HTTPException(status_code=422, detail="User must have the channel_manager role")

    existing = (
        db.query(PartnerChannelManager)
        .filter(
            PartnerChannelManager.partner_org_id == partner_id,
            PartnerChannelManager.user_id == user_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Channel manager already assigned to this partner")

    row = PartnerChannelManager(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        user_id=user_id,
        assigned_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit_event(
        db=db, actor=current_user, action="partner.channel_manager_assigned",
        object_type="partner_organization", object_id=partner_id,
        after={"user_id": str(user_id)}, ip_address=_client_ip(request),
    )
    return _serialize(row, target)


@router.delete("/partners/{partner_id}/channel-managers/{user_id}")
def unassign_channel_manager(
    partner_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unassign a channel manager. system_admin + channel_ops_admin only."""
    if UserRole(current_user.role) not in _ASSIGN_ROLES:
        raise HTTPException(status_code=403, detail="Only system_admin or channel_ops_admin may unassign channel managers")
    _partner_or_404(db, partner_id)
    row = (
        db.query(PartnerChannelManager)
        .filter(
            PartnerChannelManager.partner_org_id == partner_id,
            PartnerChannelManager.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(row)
    db.commit()

    log_audit_event(
        db=db, actor=current_user, action="partner.channel_manager_unassigned",
        object_type="partner_organization", object_id=partner_id,
        after={"user_id": str(user_id)}, ip_address=_client_ip(request),
    )
    return {"unassigned": True, "partner_org_id": str(partner_id), "user_id": str(user_id)}
