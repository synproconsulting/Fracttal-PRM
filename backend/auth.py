import os
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from roles import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "168"))

token_blacklist: set = set()


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    if token in token_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated",
        )
    try:
        # S2 (FPRM-452): pin the signing algorithm explicitly. Passing a single-
        # element ``algorithms`` list makes PyJWT reject any client-supplied
        # ``alg`` from the token header — including ``none`` and HS/RS
        # algorithm-confusion attacks — and only accept JWT_ALGORITHM (HS256).
        # Never widen this list or omit it.
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        user_uuid = _uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token",
        )
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    try:
        UserRole(user.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User has unknown role: {user.role}",
        )
    return user


def invalidate_token(token: str) -> None:
    token_blacklist.add(token)


def get_optional_bearer_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve the User from an optional ``Authorization: Bearer <jwt>`` header.

    Unlike ``get_current_user``, this never raises — it returns ``None`` when
    the header is missing, malformed, the token cannot be decoded, the
    subject is unparseable, or the user is missing/inactive.

    Used by dual-auth endpoints (draft_token query param OR Bearer JWT) so the
    bearer path is overridable via ``app.dependency_overrides`` in tests
    (FPRM-104).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        user_uuid = _uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user or not user.is_active:
        return None
    return user
