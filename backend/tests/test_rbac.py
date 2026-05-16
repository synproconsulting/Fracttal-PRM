import uuid
from unittest.mock import MagicMock

from roles import UserRole
from permissions import get_partner_org_filter, has_permission


def make_user(role: str, partner_org_id=None):
    user = MagicMock()
    user.role = role
    user.partner_org_id = partner_org_id or uuid.uuid4()
    return user


def test_partner_user_gets_org_filter():
    org_id = uuid.uuid4()
    user = make_user(UserRole.partner_user, org_id)
    filters = get_partner_org_filter(user)
    assert filters == {"partner_org_id": org_id}


def test_partner_admin_gets_org_filter():
    org_id = uuid.uuid4()
    user = make_user(UserRole.partner_admin, org_id)
    filters = get_partner_org_filter(user)
    assert filters == {"partner_org_id": org_id}


def test_channel_manager_gets_no_filter():
    user = make_user(UserRole.channel_manager)
    filters = get_partner_org_filter(user)
    assert filters == {}


def test_system_admin_gets_no_filter():
    user = make_user(UserRole.system_admin)
    filters = get_partner_org_filter(user)
    assert filters == {}


def test_tenant_isolation_different_orgs():
    org_1 = uuid.uuid4()
    org_2 = uuid.uuid4()
    user_1 = make_user(UserRole.partner_user, org_1)
    user_2 = make_user(UserRole.partner_user, org_2)
    filter_1 = get_partner_org_filter(user_1)
    filter_2 = get_partner_org_filter(user_2)
    assert filter_1["partner_org_id"] != filter_2["partner_org_id"]


def test_require_permission_grant():
    assert has_permission(UserRole.partner_user, "deal_registration:create")


def test_require_permission_deny():
    assert not has_permission(UserRole.partner_user, "deal_registration:read_all")


def test_channel_ops_admin_full_access():
    for perm in [
        "partner_organization:create",
        "deal_registration:approve",
        "asset:delete",
        "system_config:update_all",
    ]:
        assert has_permission(UserRole.channel_ops_admin, perm), f"Missing: {perm}"
