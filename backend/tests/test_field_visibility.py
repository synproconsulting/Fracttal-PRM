import uuid
from unittest.mock import MagicMock

from field_visibility import filter_sensitive_fields, is_field_visible
from roles import UserRole


def make_user(role: str):
    user = MagicMock()
    user.role = role
    user.partner_org_id = uuid.uuid4()
    return user


FULL_RESPONSE = {
    "id": "some-uuid",
    "deal_name": "Acme Corp Deal",
    "discount_rate": 0.15,
    "margin_pct": 0.42,
    "commission_rate_y1": 0.50,
    "commission_rate_y2_plus": 0.30,
    "internal_notes": "Partner is struggling with enterprise deals",
    "cost_price": 8500.00,
    "status": "pending",
}


def test_partner_user_cannot_see_margin():
    user = make_user(UserRole.partner_user)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "margin_pct" not in result


def test_partner_user_cannot_see_internal_notes():
    user = make_user(UserRole.partner_user)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "internal_notes" not in result


def test_partner_user_cannot_see_cost_price():
    user = make_user(UserRole.partner_user)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "cost_price" not in result


def test_partner_user_can_see_own_commission():
    user = make_user(UserRole.partner_user)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "commission_rate_y1" in result
    assert "commission_rate_y2_plus" in result


def test_partner_user_can_see_discount_rate():
    user = make_user(UserRole.partner_user)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "discount_rate" in result


def test_partner_admin_same_restrictions_as_partner_user():
    user = make_user(UserRole.partner_admin)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "margin_pct" not in result
    assert "internal_notes" not in result


def test_channel_manager_sees_all_fields():
    user = make_user(UserRole.channel_manager)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    for key in FULL_RESPONSE:
        assert key in result


def test_system_admin_sees_all_fields():
    user = make_user(UserRole.system_admin)
    result = filter_sensitive_fields(FULL_RESPONSE, user)
    assert "margin_pct" in result
    assert "internal_notes" in result
    assert "cost_price" in result


def test_non_sensitive_fields_always_present():
    for role in [UserRole.partner_user, UserRole.channel_manager]:
        user = make_user(role)
        result = filter_sensitive_fields(FULL_RESPONSE, user)
        assert "id" in result
        assert "deal_name" in result
        assert "status" in result


def test_is_field_visible_partner():
    user = make_user(UserRole.partner_user)
    assert not is_field_visible("margin_pct", user)
    assert is_field_visible("commission_rate_y1", user)
    assert is_field_visible("deal_name", user)


def test_is_field_visible_internal():
    user = make_user(UserRole.system_admin)
    assert is_field_visible("margin_pct", user)
    assert is_field_visible("internal_notes", user)
