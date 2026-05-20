"""Sprint 12 / FPRM-194 — internal user management endpoints.

Allows ``system_admin`` to list internal users, invite new internal accounts,
change roles, disable, and reactivate. Covers FR-SEC-004 and FR-NFR-001.

All endpoints require ``system_admin``. Internal users are any User row whose
``role`` is NOT in ``PARTNER_ROLES`` (i.e. anything other than ``partner_user``
or ``partner_admin``).

Routes (prefix ``/internal/users``):
    GET    /                        list internal users (paginated, filterable)
    GET    /{user_id}               single internal user
    POST   /invite                  create + email-invite a new internal user
    PATCH  /{user_id}/role          change role (cannot change own role,
                                    cannot demote the last system_admin)
    POST   /{user_id}/disable       set is_active=False (cannot disable self)
    POST   /{user_id}/reactivate    set is_active=True
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user, hash_password
from csv_export import csv_response
from database import get_db
from models import PasswordResetToken, User
from notifications import send_email
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole


router = APIRouter(prefix="/internal/users", tags=["internal-users"])


# --------------------------------------------------------------- helpers


def require_system_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.system_admin.value:
        raise HTTPException(status_code=403, detail="system_admin access required")
    return current_user


def _serialize(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _internal_user_or_404(user_id: uuid.UUID, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role in {r.value for r in PARTNER_ROLES}:
        raise HTTPException(status_code=404, detail="Internal user not found")
    return user


def _frontend_url() -> str:
    return os.getenv(
        "FRONTEND_URL",
        "https://fracttal-prm-frontend-production.up.railway.app",
    ).rstrip("/")


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# --------------------------------------------------------------- payloads


class InviteRequest(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None


class RoleChangeRequest(BaseModel):
    role: UserRole


# --------------------------------------------------------------- routes


@router.get("")
def list_internal_users(
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    export: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_admin),
):
    internal_role_values = {r.value for r in INTERNAL_ROLES}
    query = db.query(User).filter(User.role.in_(internal_role_values))
    if role is not None:
        if role not in internal_role_values:
            raise HTTPException(
                status_code=422,
                detail=f"role must be one of {sorted(internal_role_values)}",
            )
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if export == "csv":
        csv_rows = query.order_by(User.created_at.desc()).all()
        return csv_response(
            "users_export",
            ["Email", "Full Name", "Role", "Is Active", "Last Login", "Created Date"],
            [
                [
                    u.email or "",
                    u.full_name or "",
                    u.role or "",
                    "Yes" if u.is_active else "No",
                    u.last_login_at.isoformat() if u.last_login_at else "",
                    u.created_at.date().isoformat() if u.created_at else "",
                ]
                for u in csv_rows
            ],
        )

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_serialize(u) for u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{user_id}")
def get_internal_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_admin),
):
    return _serialize(_internal_user_or_404(user_id, db))


@router.post("/invite", status_code=201)
def invite_internal_user(
    req: InviteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    if req.role.value in {r.value for r in PARTNER_ROLES}:
        raise HTTPException(
            status_code=422,
            detail="Internal invites cannot grant partner roles",
        )

    existing = db.query(User).filter(User.email == req.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Random unguessable password so the user cannot log in until they reset.
    user = User(
        id=uuid.uuid4(),
        email=req.email,
        hashed_password=hash_password(uuid.uuid4().hex + uuid.uuid4().hex),
        full_name=req.full_name,
        role=req.role.value,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()

    reset_token = PasswordResetToken(
        id=uuid.uuid4(),
        token=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(reset_token)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor=current_user,
        action="internal_user.invited",
        object_type="user",
        object_id=user.id,
        after={"email": user.email, "role": user.role},
        ip_address=_client_ip(request),
    )

    invite_url = f"{_frontend_url()}/reset-password?token={reset_token.token}"
    try:
        send_email(
            to=user.email,
            subject="Welcome to Fracttal PRM — Set your password",
            body_html=(
                f"<p>Hi {user.full_name or 'there'},</p>"
                f"<p>You have been invited to the Fracttal PRM internal team as "
                f"<strong>{user.role}</strong>.</p>"
                f"<p>To activate your account, set your password here:</p>"
                f'<p><a href="{invite_url}">Set my password</a></p>'
                f"<p>This link expires in 7 days.</p>"
            ),
        )
    except Exception:  # pragma: no cover  — email failures must not fail the endpoint
        pass

    return _serialize(user)


@router.patch("/{user_id}/role")
def change_internal_user_role(
    user_id: uuid.UUID,
    req: RoleChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    target = _internal_user_or_404(user_id, db)
    if req.role.value in {r.value for r in PARTNER_ROLES}:
        raise HTTPException(
            status_code=422,
            detail="Cannot demote an internal user to a partner role",
        )

    if target.role == UserRole.system_admin.value and req.role != UserRole.system_admin:
        remaining = (
            db.query(User)
            .filter(User.role == UserRole.system_admin.value, User.is_active == True)  # noqa: E712
            .count()
        )
        if remaining <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last active system_admin",
            )

    before_role = target.role
    if before_role == req.role.value:
        return _serialize(target)

    target.role = req.role.value
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    log_audit_event(
        db=db,
        actor=current_user,
        action="internal_user.role_changed",
        object_type="user",
        object_id=target.id,
        before={"role": before_role},
        after={"role": target.role},
        ip_address=_client_ip(request),
    )
    return _serialize(target)


@router.post("/{user_id}/disable")
def disable_internal_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    target = _internal_user_or_404(user_id, db)
    if target.is_active is False:
        return _serialize(target)
    target.is_active = False
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    log_audit_event(
        db=db,
        actor=current_user,
        action="internal_user.disabled",
        object_type="user",
        object_id=target.id,
        before={"is_active": True},
        after={"is_active": False},
        ip_address=_client_ip(request),
    )
    return _serialize(target)


@router.post("/{user_id}/reactivate")
def reactivate_internal_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    target = _internal_user_or_404(user_id, db)
    if target.is_active is True:
        return _serialize(target)
    target.is_active = True
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    log_audit_event(
        db=db,
        actor=current_user,
        action="internal_user.reactivated",
        object_type="user",
        object_id=target.id,
        before={"is_active": False},
        after={"is_active": True},
        ip_address=_client_ip(request),
    )
    return _serialize(target)
