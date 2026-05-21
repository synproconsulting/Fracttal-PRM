"""Sprint 12 / FPRM-202 — internal-admin view of partner users across all orgs.

Distinct from ``partner_users_router.py`` (the per-tenant `/partners/{id}/users/*`
surface used by partner_admins for their own org). This router exposes a
cross-org administration surface used by `system_admin` and
`channel_ops_admin` from the InternalLayout UI.

Routes (prefix ``/internal/partner-users``):
    GET    /                        list all partner users (paginated, filterable)
    PATCH  /{user_id}/role          partner_user <-> partner_admin only
    POST   /{user_id}/disable       set is_active=False
    POST   /{user_id}/reactivate    set is_active=True
    POST   /invite                  invite to a specified partner org
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user
from csv_export import csv_response
from database import get_db
from sorting import apply_sort
from models import (
    InvitedRole,
    PartnerOrganization,
    PartnerUserInvite,
    User,
)
from roles import PARTNER_ROLES, UserRole


router = APIRouter(prefix="/internal/partner-users", tags=["internal-partner-users"])


INVITE_EXPIRY_HOURS = 72
INTERNAL_ADMIN_ROLES = {UserRole.system_admin, UserRole.channel_ops_admin}


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def require_internal_admin(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role not in INTERNAL_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="system_admin or channel_ops_admin role required",
        )
    return current_user


def _serialize_user(u: User, *, org_name: Optional[str] = None) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "partner_org_id": str(u.partner_org_id) if u.partner_org_id else None,
        "partner_org_name": org_name,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _partner_user_or_404(user_id: uuid.UUID, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role not in {r.value for r in PARTNER_ROLES}:
        raise HTTPException(status_code=404, detail="Partner user not found")
    return user


class RoleChangeRequest(BaseModel):
    role: str


class InviteRequest(BaseModel):
    email: EmailStr
    partner_org_id: uuid.UUID
    invited_role: InvitedRole


# Outer-join to PartnerOrganization so ``partner_org`` can sort by org name.
_PARTNER_USER_SORT = {
    "email": User.email,
    "full_name": User.full_name,
    "role": User.role,
    "partner_org": PartnerOrganization.legal_name,
    "status": User.is_active,
    "created_at": User.created_at,
}


@router.get("")
def list_partner_users(
    partner_org_id: Optional[uuid.UUID] = Query(default=None),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    export: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_dir: Optional[str] = Query(default="desc"),
    db: Session = Depends(get_db),
    _: User = Depends(require_internal_admin),
):
    partner_role_values = {r.value for r in PARTNER_ROLES}
    query = (
        db.query(User)
        .outerjoin(PartnerOrganization, PartnerOrganization.id == User.partner_org_id)
        .filter(User.role.in_(partner_role_values))
    )
    if partner_org_id is not None:
        query = query.filter(User.partner_org_id == partner_org_id)
    if role is not None:
        if role not in partner_role_values:
            raise HTTPException(
                status_code=422,
                detail=f"role must be one of {sorted(partner_role_values)}",
            )
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if export == "csv":
        csv_rows = query.order_by(User.created_at.desc()).all()
        csv_org_ids = {u.partner_org_id for u in csv_rows if u.partner_org_id is not None}
        csv_org_name_map: dict = {}
        if csv_org_ids:
            for o in db.query(PartnerOrganization).filter(PartnerOrganization.id.in_(csv_org_ids)).all():
                csv_org_name_map[o.id] = o.legal_name
        return csv_response(
            "partner_users_export",
            ["Email", "Full Name", "Role", "Partner Org", "Status", "Created Date"],
            [
                [
                    u.email or "",
                    u.full_name or "",
                    u.role or "",
                    csv_org_name_map.get(u.partner_org_id, "") if u.partner_org_id else "",
                    "active" if u.is_active else "disabled",
                    u.created_at.date().isoformat() if u.created_at else "",
                ]
                for u in csv_rows
            ],
        )

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed=_PARTNER_USER_SORT,
        default_col=User.created_at,
        tiebreaker=User.id,
    )
    total = query.count()
    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Resolve org names in a single follow-up query
    org_ids = {u.partner_org_id for u in rows if u.partner_org_id is not None}
    org_name_map: dict = {}
    if org_ids:
        orgs = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.id.in_(org_ids))
            .all()
        )
        org_name_map = {o.id: o.legal_name for o in orgs}

    return {
        "items": [
            _serialize_user(u, org_name=org_name_map.get(u.partner_org_id))
            for u in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{user_id}/role")
def change_partner_user_role(
    user_id: uuid.UUID,
    req: RoleChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_admin),
):
    target = _partner_user_or_404(user_id, db)
    if req.role not in {r.value for r in PARTNER_ROLES}:
        raise HTTPException(
            status_code=422,
            detail="role must be partner_user or partner_admin",
        )

    if target.role == req.role:
        return _serialize_user(target)

    before_role = target.role
    target.role = req.role
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_user.role_changed",
        object_type="user",
        object_id=target.id,
        before={"role": before_role},
        after={"role": target.role},
        ip_address=_client_ip(request),
    )
    return _serialize_user(target)


@router.post("/{user_id}/disable")
def disable_partner_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_admin),
):
    target = _partner_user_or_404(user_id, db)
    if target.is_active is False:
        return _serialize_user(target)
    target.is_active = False
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_user.disabled",
        object_type="user",
        object_id=target.id,
        before={"is_active": True},
        after={"is_active": False},
        ip_address=_client_ip(request),
    )
    return _serialize_user(target)


@router.post("/{user_id}/reactivate")
def reactivate_partner_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_admin),
):
    target = _partner_user_or_404(user_id, db)
    if target.is_active is True:
        return _serialize_user(target)
    target.is_active = True
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_user.reactivated",
        object_type="user",
        object_id=target.id,
        before={"is_active": False},
        after={"is_active": True},
        ip_address=_client_ip(request),
    )
    return _serialize_user(target)


@router.post("/invite", status_code=201)
def invite_partner_user_internal(
    req: InviteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_admin),
):
    partner = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == req.partner_org_id)
        .first()
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner organisation not found")

    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=req.partner_org_id,
        email=req.email,
        invited_role=req.invited_role,
        token=str(uuid.uuid4()),
        invited_by_user_id=current_user.id,
        expires_at=datetime.utcnow() + timedelta(hours=INVITE_EXPIRY_HOURS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_user.invite_sent",
        object_type="partner_user_invite",
        object_id=invite.id,
        after={
            "partner_org_id": str(invite.partner_org_id),
            "email": invite.email,
            "invited_role": invite.invited_role.value,
            "expires_at": invite.expires_at.isoformat(),
        },
        ip_address=_client_ip(request),
    )
    return {
        "id": str(invite.id),
        "partner_org_id": str(invite.partner_org_id),
        "email": invite.email,
        "invited_role": invite.invited_role.value,
        "token": invite.token,
        "expires_at": invite.expires_at.isoformat(),
    }
