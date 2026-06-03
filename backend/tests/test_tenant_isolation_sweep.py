"""Sprint 25 PR B / FPRM-457 — tenant-isolation regression sweep (test-only).

Defensive assurance of AD-9 / AD-33: a user from org A must NOT be able to read
or act on a resource owned by org B. One canonical parametrised list (mirroring
`CM_SCOPED_ACTIONS`) so a new partner-scoped endpoint is one line to add. Every
endpoint here must deny cross-tenant access with 403 or 404 — a 200 would be a
real leak and fails the sweep (then: STOP, file a Jira bug, fix separately).

Test-only — no production code is changed by this story.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_current_user
from database import SessionLocal
from models import (
    DealRegistration,
    PartnerCategory,
    PartnerOrganization,
    PartnerProfile,
    ProgramType,
    Quote,
    User,
)


def _make_org(db):
    o = PartnerOrganization(id=uuid.uuid4(), legal_name=f"Iso {uuid.uuid4().hex[:5]}",
                            program_type=ProgramType.distributor,
                            partner_category=PartnerCategory.reseller, status="active")
    db.add(o); db.commit(); db.refresh(o)
    return o


def _user(db, role, org_id=None):
    u = User(id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@t.com",
             hashed_password="x", role=role, is_active=True, partner_org_id=org_id)
    db.add(u); db.commit(); db.refresh(u); db.expunge(u)
    return u


# Each builder creates the resource on org `b` and returns (method, url, body).
def b_partner_detail(db, b):
    return "get", f"/partners/{b.id}", None


def b_profile_get(db, b):
    db.add(PartnerProfile(id=uuid.uuid4(), partner_org_id=b.id)); db.commit()
    return "get", f"/partner-profiles/{b.id}", None


def b_profile_patch(db, b):
    db.add(PartnerProfile(id=uuid.uuid4(), partner_org_id=b.id)); db.commit()
    return "patch", f"/partner-profiles/{b.id}", {"year_established": 2000}


def b_activation(db, b):
    return "get", f"/partners/{b.id}/activation", None


def b_activation_criteria(db, b):
    return "get", f"/partners/{b.id}/activation/criteria", None


def b_dashboard_summary(db, b):
    return "get", f"/partners/{b.id}/dashboard/summary", None


def b_commission_rates(db, b):
    return "get", f"/partners/{b.id}/commission-rates", None


def b_pipeline(db, b):
    return "get", f"/partners/{b.id}/pipeline", None


def b_partner_users(db, b):
    return "get", f"/partners/{b.id}/users", None


def b_documents(db, b):
    return "get", f"/partners/{b.id}/documents", None


def b_deal_detail(db, b):
    d = DealRegistration(id=uuid.uuid4(), partner_org_id=b.id, status="submitted",
                         customer_name="C", deal_name="D")
    db.add(d); db.commit()
    return "get", f"/deal-registrations/{d.id}", None


def b_quote_detail(db, b):
    creator = _user(db, "system_admin")
    d = DealRegistration(id=uuid.uuid4(), partner_org_id=b.id, status="approved",
                         customer_name="C", deal_name="D")
    db.add(d); db.commit()
    q = Quote(id=uuid.uuid4(), deal_id=d.id, partner_org_id=b.id, created_by=creator.id)
    db.add(q); db.commit()
    return "get", f"/quotes/{q.id}", None


# Canonical list of partner-scoped endpoints — add new ones here.
PARTNER_SCOPED_ENDPOINTS = [
    ("partner_detail", b_partner_detail),
    ("profile_get", b_profile_get),
    ("profile_patch", b_profile_patch),
    ("activation", b_activation),
    ("activation_criteria", b_activation_criteria),
    ("dashboard_summary", b_dashboard_summary),
    ("commission_rates", b_commission_rates),
    ("pipeline", b_pipeline),
    ("partner_users", b_partner_users),
    ("documents", b_documents),
    ("deal_detail", b_deal_detail),
    ("quote_detail", b_quote_detail),
]


@pytest.mark.parametrize("name,builder", PARTNER_SCOPED_ENDPOINTS,
                         ids=[n for n, _ in PARTNER_SCOPED_ENDPOINTS])
def test_org_a_user_cannot_access_org_b_resource(name, builder):
    db = SessionLocal()
    try:
        a = _make_org(db)
        b = _make_org(db)
        method, url, body = builder(db, b)
        actor = _user(db, "partner_admin", org_id=a.id)  # belongs to org A
    finally:
        db.close()

    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        client = TestClient(app)
        fn = getattr(client, method)
        r = fn(url, json=body) if body is not None else fn(url)
    finally:
        app.dependency_overrides.clear()

    # Isolation must be enforced: a 200 here is a real cross-tenant leak.
    assert r.status_code != 200, f"{name}: LEAK — org A read/acted on org B (200): {r.text}"
    assert r.status_code in (403, 404), \
        f"{name}: expected 403/404 cross-tenant denial, got {r.status_code}: {r.text}"
