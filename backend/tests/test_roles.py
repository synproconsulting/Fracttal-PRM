from roles import UserRole, PARTNER_ROLES, INTERNAL_ROLES
from permissions import PERMISSIONS, has_permission


def test_all_roles_have_permissions():
    for role in UserRole:
        assert len(PERMISSIONS.get(role, set())) > 0, f"{role} has no permissions"


def test_partner_user_cannot_read_all_partners():
    assert not has_permission(UserRole.partner_user, "partner_organization:read_all")


def test_partner_user_cannot_approve_deals():
    assert not has_permission(UserRole.partner_user, "deal_registration:approve")


def test_partner_admin_cannot_read_all_partners():
    assert not has_permission(UserRole.partner_admin, "partner_organization:read_all")


def test_channel_manager_can_approve_deals():
    assert has_permission(UserRole.channel_manager, "deal_registration:approve")


def test_system_admin_has_user_management():
    assert has_permission(UserRole.system_admin, "user_management:create")
    assert has_permission(UserRole.system_admin, "user_management:delete")


def test_finance_approver_can_approve_quotes():
    assert has_permission(UserRole.finance_approver, "quote:approve")


def test_finance_approver_cannot_manage_users():
    assert not has_permission(UserRole.finance_approver, "user_management:create")


def test_partner_roles_set():
    assert UserRole.partner_user in PARTNER_ROLES
    assert UserRole.partner_admin in PARTNER_ROLES
    assert UserRole.channel_manager not in PARTNER_ROLES


def test_internal_roles_set():
    assert UserRole.channel_manager in INTERNAL_ROLES
    assert UserRole.system_admin in INTERNAL_ROLES
    assert UserRole.partner_user not in INTERNAL_ROLES
