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
