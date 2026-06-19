"""Partner user management endpoints (FPRM-56).

Allows Partner Admins to invite/disable/manage users within their own org, and
Channel Ops Admins to do the same for any partner.

Permissions:
    POST   /partners/{partner_id}/users/invite           - partner_admin (own org) or channel_ops_admin
    GET    /partners/{partner_id}/users                  - any auth (tenant-scoped)
    PATCH  /partners/{partner_id}/users/{user_id}        - partner_admin (own org) or channel_ops_admin
"""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import (
    InvitedRole,
    PartnerOrganization,
    PartnerUserInvite,
    User,
)
from roles import PARTNER_ROLES, UserRole
from notifications import send_email, public_app_url

router = APIRouter(prefix="/partners", tags=["partner-users"])

INVITE_EXPIRY_HOURS = 72


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _serialize_user(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "partner_org_id": str(u.partner_org_id) if u.partner_org_id else None,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _serialize_invite(inv: PartnerUserInvite) -> dict:
    return {c.name: getattr(inv, c.name) for c in inv.__table__.columns}


def _check_management_access(current_user: User, partner_id: uuid.UUID) -> None:
    role = UserRole(current_user.role)
    if role == UserRole.partner_admin:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in {UserRole.channel_ops_admin, UserRole.system_admin}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


class InviteRequest(BaseModel):
    email: EmailStr
    invited_role: InvitedRole


@router.post("/{partner_id}/users/invite", status_code=201)
def invite_partner_user(
    partner_id: uuid.UUID,
    req: InviteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_management_access(current_user, partner_id)
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    token = str(uuid.uuid4())
    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        email=req.email,
        invited_role=req.invited_role,
        token=token,
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

    # FPRM-462 — deliver the invite via Resend (stdout fallback in dev). Wrapped
    # per AD-13 so an email failure never breaks the invite creation.
    try:
        send_email(
            to=invite.email,
            subject="You've been invited to Fracttal PRM",
            body_html=(
                f"<p>You've been invited to join Fracttal PRM as a partner user.</p>"
                f"<p><a href='{public_app_url()}/accept-invite?token={invite.token}'>"
                f"Accept invitation</a></p>"
                f"<p>This invitation expires in 72 hours.</p>"
            ),
        )
    except Exception:  # pragma: no cover — belt-and-braces; send_email never raises
        pass

    # FPRM-462 — the token now travels only via the email link; never return it in
    # the API response. Non-sensitive fields remain for the management UI.
    result = _serialize_invite(invite)
    result.pop("token", None)
    result["message"] = f"Invitation sent to {invite.email}"
    return result


@router.get("/{partner_id}/users")
def list_partner_users(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")
    users = db.query(User).filter(User.partner_org_id == partner_id).all()
    return {"items": [_serialize_user(u) for u in users]}


@router.patch("/{partner_id}/users/{user_id}")
def update_partner_user(
    partner_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_management_access(current_user, partner_id)
    target = db.query(User).filter(User.id == user_id).first()
    if not target or target.partner_org_id is None or str(target.partner_org_id) != str(partner_id):
        raise HTTPException(status_code=404, detail="User not found in this partner org")

    before = _serialize_user(target)
    changes: list[str] = []

    if "is_active" in payload:
        new_active = bool(payload["is_active"])
        if target.is_active != new_active:
            target.is_active = new_active
            changes.append("disable" if not new_active else "enable")

    if "role" in payload:
        new_role = payload["role"]
        try:
            InvitedRole(new_role)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="role must be partner_user or partner_admin",
            )
        if target.role != new_role:
            target.role = new_role
            changes.append("role_change")

    if "full_name" in payload:
        target.full_name = payload["full_name"]

    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    after = _serialize_user(target)
    for change in changes:
        if change == "disable":
            action = "partner_user.disabled"
        elif change == "enable":
            action = "partner_user.enabled"
        else:
            action = "partner_user.role_changed"
        log_audit_event(
            db=db,
            actor=current_user,
            action=action,
            object_type="user",
            object_id=target.id,
            before=before,
            after=after,
            ip_address=_client_ip(request),
        )
    if not changes:
        log_audit_event(
            db=db,
            actor=current_user,
            action="partner_user.update",
            object_type="user",
            object_id=target.id,
            before=before,
            after=after,
            ip_address=_client_ip(request),
        )
    return after
