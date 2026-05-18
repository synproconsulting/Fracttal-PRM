import os
import sys
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from audit import log_audit_event
from roles import UserRole


def make_user(role=UserRole.system_admin):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = role
    user.partner_org_id = uuid.uuid4()
    return user


def test_log_audit_event_creates_entry():
    """log_audit_event must create an AuditLog entry with correct fields."""
    mock_db = MagicMock()
    actor = make_user()

    log_audit_event(
        db=mock_db,
        actor=actor,
        action="partner_profile.update",
        object_type="partner_organization",
        object_id=uuid.uuid4(),
        before={"status": "applicant"},
        after={"status": "active"},
        notes="Approved by channel manager",
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    added_entry = mock_db.add.call_args[0][0]
    assert added_entry.action == "partner_profile.update"
    assert added_entry.object_type == "partner_organization"
    assert added_entry.actor_id == actor.id
    assert added_entry.actor_role == actor.role
    assert added_entry.before_state == {"status": "applicant"}
    assert added_entry.after_state == {"status": "active"}


def test_log_audit_event_without_optional_fields():
    """log_audit_event must work without before/after/ip/notes."""
    mock_db = MagicMock()
    actor = make_user()

    log_audit_event(
        db=mock_db,
        actor=actor,
        action="user.login",
        object_type="user",
        object_id=actor.id,
    )

    mock_db.add.assert_called_once()
    added_entry = mock_db.add.call_args[0][0]
    assert added_entry.before_state is None
    assert added_entry.after_state is None
    assert added_entry.ip_address is None


def test_log_audit_event_anonymous_actor_stores_null_actor_id():
    """FPRM-89: anonymous events must store actor_id=None (SQL null), not the string 'None'."""
    mock_db = MagicMock()

    log_audit_event(
        db=mock_db,
        actor=None,
        action="partner_application.submitted",
        object_type="partner_application",
        object_id=uuid.uuid4(),
    )

    mock_db.add.assert_called_once()
    added_entry = mock_db.add.call_args[0][0]
    assert added_entry.actor_id is None, "anonymous event must produce actor_id=None"
    assert added_entry.actor_id != "None", "actor_id must not be the string 'None'"
    assert added_entry.actor_role == "anonymous"


def test_audit_log_endpoint_serializes_null_actor_id_as_null():
    """FPRM-89: /admin/audit-log must return actor_id as JSON null, not the string 'None',
    for rows where the underlying DB value is NULL (anonymous events)."""
    from datetime import datetime as _dt
    from unittest.mock import patch

    from auth import get_current_user
    from database import get_db
    from roles import UserRole

    # Build a fake AuditLog row with actor_id=None.
    fake_row = MagicMock()
    fake_row.id = uuid.uuid4()
    fake_row.timestamp = _dt(2026, 5, 18, 12, 0, 0)
    fake_row.actor_id = None
    fake_row.actor_role = "anonymous"
    fake_row.action = "partner_application.submitted"
    fake_row.object_type = "partner_application"
    fake_row.object_id = uuid.uuid4()
    fake_row.before_state = None
    fake_row.after_state = {"status": "submitted"}
    fake_row.ip_address = "10.0.0.1"
    fake_row.notes = None

    fake_query = MagicMock()
    fake_query.order_by.return_value = fake_query
    fake_query.filter.return_value = fake_query
    fake_query.count.return_value = 1
    fake_query.offset.return_value = fake_query
    fake_query.limit.return_value = fake_query
    fake_query.all.return_value = [fake_row]

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    admin = make_user(role=UserRole.system_admin.value)

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        client = TestClient(app)
        response = client.get("/admin/audit-log", headers={"Authorization": "Bearer dummy"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["actor_id"] is None, f"actor_id should be JSON null, got: {item['actor_id']!r}"
        assert item["actor_role"] == "anonymous"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_audit_log_endpoint_requires_system_admin():
    """GET /admin/audit-log must return 401 without token."""
    client = TestClient(app)
    response = client.get("/admin/audit-log")
    assert response.status_code == 401


def test_audit_log_pagination_params_accepted():
    """Pagination query params must be accepted (401 from auth, not 422 from validation)."""
    client = TestClient(app)
    response = client.get("/admin/audit-log?page=2&page_size=25")
    assert response.status_code == 401
