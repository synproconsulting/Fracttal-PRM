"""Sprint 24 PR B / FPRM-422 + FPRM-423 / AD-41 -- channel-manager assignment
+ partner-scoped approval routing.

Covers the assignment CRUD, the shared resolver's global-fallback switch, queue
scoping on /internal/deals + /internal/quotes, and action guards. The key
invariant: while NO assignment exists anywhere, every channel_manager sees/acts
on all partners (bootstrap); the first assignment flips every CM to scoped;
system_admin + channel_ops_admin are always unscoped.
"""
import importlib.util
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerChannelManager,
    PartnerOrganization,
    ProgramType,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///./test_cm_assignment.db",
                        connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_cm_assignment.db"):
        try: os.remove("./test_cm_assignment.db")
        except OSError: pass


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        _seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in ("partner_channel_managers", "quote_line_items", "quote_versions",
                    "quotes", "feature_plan_prices", "volume_discount_tiers",
                    "deal_registrations", "users", "partner_organizations", "audit_log"):
            try: s.execute(text(f"DELETE FROM {tbl}"))
            except Exception: pass
        s.commit(); s.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_pricing(db):
    today = date(2024, 1, 1)
    db.add(FeaturePlanPrice(plan_code="starter", feature_pack_annual=Decimal("1161.00"),
                            transactional_user_annual=Decimal("540.00"),
                            limited_tech_user_annual=Decimal("240.00"), effective_from=today))
    db.add(VolumeDiscountTier(min_users=1, max_users=10,
                              transactional_user_discount_pct=Decimal("0"),
                              limited_tech_user_discount_pct=Decimal("0")))
    db.commit()


def _org(db, name=None):
    o = PartnerOrganization(id=uuid.uuid4(), legal_name=name or f"Org {uuid.uuid4().hex[:4]}",
                            program_type=ProgramType.distributor,
                            partner_category=PartnerCategory.reseller, status="active")
    db.add(o); db.commit()
    return o


def _deal(db, org_id, name=None, status="approved"):
    d = DealRegistration(id=uuid.uuid4(), partner_org_id=org_id, status=status,
                         customer_name="C", deal_name=name or "D")
    db.add(d); db.commit()
    return d


def _user(db, role, org_id=None):
    u = User(id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@t.com",
             hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
             full_name=f"{role} person")
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _quote(client, deal_id):
    r = client.post(f"/deals/{deal_id}/quotes",
                    json={"feature_plan": "starter", "qty_transactional_users": 1,
                          "qty_limited_tech_users": 0})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_migration_041_importable():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full = os.path.join(here, "alembic", "versions", "041_create_partner_channel_managers.py")
    spec = importlib.util.spec_from_file_location("mig041", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "041" and mod.down_revision == "040"
    assert hasattr(mod, "upgrade") and hasattr(mod, "downgrade")


# ===================== Assignment CRUD (S5) =====================

def test_assign_list_unassign_happy(client, db):
    org = _org(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(_user(db, UserRole.channel_ops_admin.value))
    r = client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(cm.id)})
    assert r.status_code == 201, r.text
    assert r.json()["full_name"] == cm.full_name and r.json()["email"] == cm.email
    r = client.get(f"/partners/{org.id}/channel-managers")
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    r = client.delete(f"/partners/{org.id}/channel-managers/{cm.id}")
    assert r.status_code == 200
    assert client.get(f"/partners/{org.id}/channel-managers").json()["items"] == []


def test_assign_non_channel_manager_user_422(client, db):
    org = _org(db)
    not_cm = _user(db, UserRole.sales_rep.value)
    _auth(_user(db, UserRole.system_admin.value))
    r = client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(not_cm.id)})
    assert r.status_code == 422


def test_assign_by_partner_admin_403(client, db):
    org = _org(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(_user(db, UserRole.partner_admin.value, org_id=org.id))
    r = client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(cm.id)})
    assert r.status_code == 403


def test_assign_by_channel_manager_403(client, db):
    org = _org(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(_user(db, UserRole.channel_manager.value))
    r = client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(cm.id)})
    assert r.status_code == 403


def test_assign_duplicate_409(client, db):
    org = _org(db)
    cm = _user(db, UserRole.channel_manager.value)
    _auth(_user(db, UserRole.system_admin.value))
    assert client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(cm.id)}).status_code == 201
    assert client.post(f"/partners/{org.id}/channel-managers", json={"user_id": str(cm.id)}).status_code == 409


def test_unassign_missing_404(client, db):
    org = _org(db)
    _auth(_user(db, UserRole.system_admin.value))
    r = client.delete(f"/partners/{org.id}/channel-managers/{uuid.uuid4()}")
    assert r.status_code == 404


# ===================== Routing / global switch (S6) =====================

def _assign(db, org_id, cm_id):
    db.add(PartnerChannelManager(id=uuid.uuid4(), partner_org_id=org_id, user_id=cm_id))
    db.commit()


def test_bootstrap_all_cms_see_all_deals(client, db):
    """No assignments anywhere -> every CM sees all partners' deals."""
    a, b = _org(db), _org(db)
    _deal(db, a.id); _deal(db, b.id)
    _auth(_user(db, UserRole.channel_manager.value))
    body = client.get("/internal/deals").json()
    assert body["total"] == 2


def test_scoped_cm_sees_only_assigned_deals(client, db):
    a, b = _org(db), _org(db)
    _deal(db, a.id, name="A-deal"); _deal(db, b.id, name="B-deal")
    cm = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm.id)  # first assignment -> global switch flips
    _auth(cm)
    body = client.get("/internal/deals").json()
    assert body["total"] == 1
    assert body["items"][0]["deal_name"] == "A-deal"


def test_cm_zero_assignments_empty_queue(client, db):
    a, b = _org(db), _org(db)
    _deal(db, a.id); _deal(db, b.id)
    cm1 = _user(db, UserRole.channel_manager.value)
    cm2 = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm1.id)  # assignments now exist -> cm2 (none) sees nothing
    _auth(cm2)
    assert client.get("/internal/deals").json()["total"] == 0


def test_admins_always_see_all_when_scoped(client, db):
    a, b = _org(db), _org(db)
    _deal(db, a.id); _deal(db, b.id)
    cm = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm.id)
    for role in (UserRole.channel_ops_admin.value, UserRole.system_admin.value):
        _auth(_user(db, role))
        assert client.get("/internal/deals").json()["total"] == 2


def test_cm_403_on_unassigned_deal_action(client, db):
    a, b = _org(db), _org(db)
    deal_b = _deal(db, b.id, status="conflict_detected")
    cm = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm.id)  # cm assigned to A only
    _auth(cm)
    # conflict-check on B's deal -> 403 (not assigned)
    assert client.post(f"/internal/deals/{deal_b.id}/conflict-check").status_code == 403


def test_cm_can_action_assigned_deal(client, db):
    a = _org(db)
    deal_a = _deal(db, a.id)
    cm = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm.id)
    _auth(cm)
    assert client.post(f"/internal/deals/{deal_a.id}/conflict-check").status_code == 200


def test_quote_queue_and_action_scoped(client, db):
    a, b = _org(db), _org(db)
    # build a quote on each org (via the engine) BEFORE any assignment
    _auth(_user(db, UserRole.system_admin.value))
    qa = _quote(client, _deal(db, a.id).id)
    qb = _quote(client, _deal(db, b.id).id)
    cm = _user(db, UserRole.channel_manager.value)
    _assign(db, a.id, cm.id)  # cm assigned to A only
    _auth(cm)
    # queue scoped to A's quote
    body = client.get("/internal/quotes").json()
    assert body["total"] == 1 and body["items"][0]["id"] == qa
    # status action on B's quote -> 403
    assert client.patch(f"/quotes/{qb}/status", json={"status": "sent"}).status_code == 403
    # status action on A's quote -> allowed
    assert client.patch(f"/quotes/{qa}/status", json={"status": "sent"}).status_code == 200
