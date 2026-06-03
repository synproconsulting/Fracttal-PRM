"""Sprint 25 PR B / FPRM-456 — server-side password-strength enforcement.

Unit tests for the shared validator plus integration tests proving the policy is
enforced on the invite-accept (password-set) and password-reset paths, and that
the documented credential ``TestPass123!`` still satisfies it.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import (
    InvitedRole,
    PartnerOrganization,
    PartnerUserInvite,
    PasswordResetToken,
    ProgramType,
    PartnerCategory,
    User,
)
from password_policy import validate_password_strength

client = TestClient(app)


# ---- unit -----------------------------------------------------------------

def test_documented_test_credentials_satisfy_policy():
    # These must keep working — they are the documented fixtures.
    validate_password_strength("TestPass123!")
    validate_password_strength("PartnerPass123!")


def test_compliant_password_accepted():
    validate_password_strength("Abcdefgh1234")  # 12 chars, upper/lower/digit


@pytest.mark.parametrize("weak", [
    "Short1A",            # too short
    "alllowercase1234",   # no uppercase
    "ALLUPPERCASE1234",   # no lowercase
    "NoDigitsHereAbc!",   # no digit
    "Ab1",                # too short, though has mix
])
def test_weak_password_rejected(weak):
    with pytest.raises(HTTPException) as exc:
        validate_password_strength(weak)
    assert exc.value.status_code == 422


# ---- integration ----------------------------------------------------------

def _org(db):
    o = PartnerOrganization(id=uuid.uuid4(), legal_name=f"PwOrg {uuid.uuid4().hex[:5]}",
                            program_type=ProgramType.distributor,
                            partner_category=PartnerCategory.reseller, status="active")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_accept_invite_rejects_weak_password():
    db = SessionLocal()
    try:
        org = _org(db)
        inviter = User(id=uuid.uuid4(), email=f"inv-{uuid.uuid4().hex[:6]}@t.com",
                       hashed_password="x", role="system_admin", is_active=True)
        db.add(inviter); db.commit()
        invite = PartnerUserInvite(id=uuid.uuid4(), partner_org_id=org.id,
                                   email=f"weak-{uuid.uuid4().hex[:6]}@t.com",
                                   invited_role=InvitedRole.partner_user,
                                   token=str(uuid.uuid4()), invited_by_user_id=inviter.id,
                                   expires_at=datetime.utcnow() + timedelta(hours=72))
        db.add(invite); db.commit()
        tok = invite.token
    finally:
        db.close()
    r = client.post("/auth/accept-invite",
                    json={"token": tok, "password": "weak", "full_name": "Weak P"})
    assert r.status_code == 422, r.text

    r2 = client.post("/auth/accept-invite",
                     json={"token": tok, "password": "TestPass123!", "full_name": "Strong P"})
    assert r2.status_code == 201, r2.text


def test_password_reset_confirm_rejects_weak_password():
    db = SessionLocal()
    try:
        user = User(id=uuid.uuid4(), email=f"rst-{uuid.uuid4().hex[:6]}@t.com",
                    hashed_password="x", role="partner_user", is_active=True)
        db.add(user); db.commit()
        token = PasswordResetToken(id=uuid.uuid4(), token=str(uuid.uuid4()),
                                   user_id=user.id,
                                   expires_at=datetime.utcnow() + timedelta(hours=1))
        db.add(token); db.commit()
        tok = token.token
    finally:
        db.close()
    r = client.post("/auth/password-reset/confirm",
                    json={"token": tok, "new_password": "weak"})
    assert r.status_code == 422, r.text

    r2 = client.post("/auth/password-reset/confirm",
                     json={"token": tok, "new_password": "TestPass123!"})
    assert r2.status_code == 200, r2.text
