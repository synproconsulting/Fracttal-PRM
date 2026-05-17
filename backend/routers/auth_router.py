import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import User, PasswordResetToken, PartnerUserInvite
from audit import log_audit_event
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    invalidate_token,
    oauth2_scheme,
    JWT_EXPIRY_HOURS,
)
from rate_limiter import limiter
from roles import UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_payload(user: User) -> dict:
    """JWT payload — includes partner_org_id so the partner portal can resolve
    the user's org without an extra /auth/me round-trip on every page load.
    Fixed in FPRM-119 (bundled with FPRM-106).
    """
    return {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "partner_org_id": str(user.partner_org_id) if user.partner_org_id else None,
    }


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: UserRole = UserRole.partner_user


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str | None = None


@router.post("/register", status_code=201)
@limiter.limit("10/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": str(user.id), "email": user.email}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")
    token = create_access_token(_token_payload(user))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_HOURS * 3600,
    }


@router.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    invalidate_token(token)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
def refresh(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    new_token = create_access_token(_token_payload(current_user))
    invalidate_token(token)
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_HOURS * 3600,
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "partner_org_id": str(current_user.partner_org_id) if current_user.partner_org_id else None,
    }


@router.post("/password-reset/request")
def password_reset_request(req: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        reset_token = PasswordResetToken(
            id=uuid.uuid4(),
            token=str(uuid.uuid4()),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(reset_token)
        db.commit()
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        reset_url = f"{frontend_url}/reset-password?token={reset_token.token}"
        print(f"[PASSWORD RESET] Reset URL for {req.email}: {reset_url}")
    return {"message": "If that email exists, a reset link has been sent"}


@router.post("/accept-invite", status_code=201)
def accept_invite(req: AcceptInviteRequest, request: Request, db: Session = Depends(get_db)):
    invite = db.query(PartnerUserInvite).filter(PartnerUserInvite.token == req.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invite already accepted")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite has expired")

    existing = db.query(User).filter(User.email == invite.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=uuid.uuid4(),
        email=invite.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=invite.invited_role.value,
        partner_org_id=invite.partner_org_id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    invite.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor=user,
        action="partner_user.invite_accepted",
        object_type="user",
        object_id=user.id,
        after={
            "email": user.email,
            "role": user.role,
            "partner_org_id": str(user.partner_org_id),
            "invite_id": str(invite.id),
        },
        ip_address=request.client.host if request.client else None,
    )

    token = create_access_token(_token_payload(user))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRY_HOURS * 3600,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "partner_org_id": str(user.partner_org_id),
        },
    }


@router.post("/password-reset/confirm")
def password_reset_confirm(req: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token
    ).first()
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if token_record.used:
        raise HTTPException(status_code=400, detail="Reset token has already been used")
    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")
    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    user.hashed_password = hash_password(req.new_password)
    token_record.used = True
    db.commit()
    return {"message": "Password reset successfully"}
