"""Tests for partner activities router (FPRM-57)."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    ActivityType,
    AuditLog,
    PartnerActivity,
    PartnerOrganization,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///./test_activities.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_activities.db"):
        try:
            os.remove("./test_activities.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user(role, partner_org_id=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@t.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def make_partner():
    return PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"P {uuid.uuid4().hex[:6]}",
        program_type="distributor",
        partner_category="master",
        status="active",
        monthly_fee_status="current",
    )


def override(db, user):
    def _db():
        yield db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user


def clear():
    app.dependency_overrides.clear()


def test_create_activity_as_channel_manager(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()

    override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/activities",
            json={"activity_type": "note", "title": "First sync", "body": "Met on call"},
        )
    finally:
        clear()
    assert r.status_code == 201
    data = r.json()
    assert data["activity_type"] == "note"
    assert data["is_internal"] is True


def test_create_activity_denied_for_partner_admin(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    pa = make_user(UserRole.partner_admin, partner.id)
    db_session.add(pa)
    db_session.commit()

    override(db_session, pa)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/activities",
            json={"activity_type": "note", "title": "X"},
        )
    finally:
        clear()
    assert r.status_code == 403


def test_internal_note_hidden_from_partner_user(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()
    # Internal note (is_internal=True)
    internal = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.note,
        title="Internal only",
        created_by_user_id=cm.id,
        is_internal=True,
    )
    # External note
    external = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.note,
        title="Shared with partner",
        created_by_user_id=cm.id,
        is_internal=False,
    )
    db_session.add_all([internal, external])
    db_session.commit()
    pu = make_user(UserRole.partner_user, partner.id)
    db_session.add(pu)
    db_session.commit()

    override(db_session, pu)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activities")
    finally:
        clear()
    assert r.status_code == 200
    titles = [a["title"] for a in r.json()["items"]]
    assert "Shared with partner" in titles
    assert "Internal only" not in titles


def test_internal_user_sees_all_activities(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()
    internal = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.note,
        title="Internal note",
        created_by_user_id=cm.id,
        is_internal=True,
    )
    db_session.add(internal)
    db_session.commit()

    override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{partner.id}/activities")
    finally:
        clear()
    assert r.status_code == 200
    titles = [a["title"] for a in r.json()["items"]]
    assert "Internal note" in titles


def test_update_activity_by_creator(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()
    a = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.task,
        title="Old title",
        created_by_user_id=cm.id,
        is_internal=True,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)

    override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/activities/{a.id}",
            json={"title": "New title", "body": "Updated"},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["title"] == "New title"


def test_update_activity_by_non_creator_denied(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()
    a = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.note,
        title="Someone else's",
        created_by_user_id=cm.id,
        is_internal=True,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    other_cm = make_user(UserRole.channel_manager)
    db_session.add(other_cm)
    db_session.commit()

    override(db_session, other_cm)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/activities/{a.id}",
            json={"title": "Hijacked"},
        )
    finally:
        clear()
    assert r.status_code == 403


def test_channel_ops_admin_can_update_others_activity(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()
    a = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner.id,
        activity_type=ActivityType.note,
        title="Original",
        created_by_user_id=cm.id,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    ops = make_user(UserRole.channel_ops_admin)
    db_session.add(ops)
    db_session.commit()

    override(db_session, ops)
    try:
        client = TestClient(app)
        r = client.patch(
            f"/partners/{partner.id}/activities/{a.id}",
            json={"title": "Edited by ops"},
        )
    finally:
        clear()
    assert r.status_code == 200
    assert r.json()["title"] == "Edited by ops"


def test_partner_user_tenant_isolation_on_list(db_session):
    p_a = make_partner()
    p_b = make_partner()
    db_session.add_all([p_a, p_b])
    db_session.commit()
    db_session.refresh(p_a)
    db_session.refresh(p_b)
    pu_b = make_user(UserRole.partner_user, p_b.id)
    db_session.add(pu_b)
    db_session.commit()

    override(db_session, pu_b)
    try:
        client = TestClient(app)
        r = client.get(f"/partners/{p_a.id}/activities")
    finally:
        clear()
    assert r.status_code == 403


def test_audit_log_on_activity_create(db_session):
    partner = make_partner()
    db_session.add(partner)
    db_session.commit()
    db_session.refresh(partner)
    cm = make_user(UserRole.channel_manager)
    db_session.add(cm)
    db_session.commit()

    override(db_session, cm)
    try:
        client = TestClient(app)
        r = client.post(
            f"/partners/{partner.id}/activities",
            json={"activity_type": "call", "title": "Audited call"},
        )
    finally:
        clear()
    assert r.status_code == 201
    new_id = uuid.UUID(r.json()["id"])
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "partner_activity.create", AuditLog.object_id == new_id)
        .first()
    )
    assert entry is not None
