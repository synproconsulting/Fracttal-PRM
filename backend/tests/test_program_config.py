"""Sprint 13 — tests for /internal/config endpoints (FPRM-209 + FPRM-213).

Tests run against sqlite via Base.metadata.create_all — alembic migrations
do not run in CI. The seed rows that migration 021/022 install on Railway
are reproduced here in the `seeded_workflow_steps`, `seeded_tiers`, and
`seeded_activation_criteria` fixtures so the tests reflect production state.
"""
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
from models import ApprovalWorkflowStep, User
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_program_config.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_program_config.db"):
        try:
            os.remove("./test_program_config.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _make_user(db, role: UserRole) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        role=role.value,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture()
def seeded_workflow_steps(db_session):
    """Mirror migration 021 seed inserts."""
    rows = [
        ApprovalWorkflowStep(
            id=uuid.uuid4(),
            workflow_type="partner_application",
            step_order=1,
            step_name="Channel Ops Review",
            required_role=UserRole.channel_ops_admin.value,
            is_active=True,
        ),
        ApprovalWorkflowStep(
            id=uuid.uuid4(),
            workflow_type="deal_registration",
            step_order=1,
            step_name="Channel Manager Review",
            required_role=UserRole.channel_manager.value,
            is_active=True,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


# ---- Approval workflow step tests ----------------------------------------


def test_list_approval_steps(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.get("/internal/config/approval-steps")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    types = {i["workflow_type"] for i in items}
    assert types == {"partner_application", "deal_registration"}


def test_filter_by_workflow_type(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    r = client.get("/internal/config/approval-steps?workflow_type=deal_registration")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["workflow_type"] == "deal_registration"


def test_create_approval_step(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "partner_application",
        "step_order": 2,
        "step_name": "Channel Manager Sign-off",
        "required_role": "channel_manager",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["step_name"] == "Channel Manager Sign-off"
    assert body["step_order"] == 2


def test_create_step_invalid_workflow_type(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "banana",
        "step_order": 1,
        "step_name": "Whatever",
        "required_role": "channel_manager",
    })
    assert r.status_code == 400, r.text


def test_create_step_invalid_role(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.post("/internal/config/approval-steps", json={
        "workflow_type": "partner_application",
        "step_order": 1,
        "step_name": "Step",
        "required_role": "not_a_role",
    })
    assert r.status_code == 400, r.text


def test_patch_approval_step(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_workflow_steps[0]
    r = client.patch(f"/internal/config/approval-steps/{target.id}", json={
        "step_name": "Renamed Step",
    })
    assert r.status_code == 200, r.text
    assert r.json()["step_name"] == "Renamed Step"


def test_delete_approval_step_as_system_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.system_admin))
    target = seeded_workflow_steps[1]
    r = client.delete(f"/internal/config/approval-steps/{target.id}")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    # After deletion, the row is filtered out of the list by default
    r2 = client.get("/internal/config/approval-steps")
    assert all(i["id"] != str(target.id) for i in r2.json()["items"])


def test_delete_forbidden_for_channel_ops_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.channel_ops_admin))
    target = seeded_workflow_steps[0]
    r = client.delete(f"/internal/config/approval-steps/{target.id}")
    assert r.status_code == 403, r.text


def test_list_forbidden_for_partner_admin(client, db_session, seeded_workflow_steps):
    _as(_make_user(db_session, UserRole.partner_admin))
    r = client.get("/internal/config/approval-steps")
    assert r.status_code == 403, r.text


def test_patch_unknown_step_returns_404(client, db_session):
    _as(_make_user(db_session, UserRole.system_admin))
    r = client.patch(
        f"/internal/config/approval-steps/{uuid.uuid4()}",
        json={"step_name": "X"},
    )
    assert r.status_code == 404, r.text
