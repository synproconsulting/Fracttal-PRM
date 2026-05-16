"""
Field-level visibility control for Fracttal PRM API responses.

Sensitive fields are stripped from response dicts when the requesting
user's role does not have visibility rights.

Partner-side roles (partner_user, partner_admin) CANNOT see:
    - margin_pct       - Fracttal's internal margin
    - internal_notes   - Internal Fracttal notes on partner/deal
    - cost_price       - Internal cost pricing

Partner-side roles CAN see (it's their own commission/discount data):
    - commission_rate_y1
    - commission_rate_y2_plus
    - discount_rate

Internal roles see ALL fields.
"""
from roles import UserRole, PARTNER_ROLES

PARTNER_HIDDEN_FIELDS = {
    "margin_pct",
    "internal_notes",
    "cost_price",
}

PARTNER_VISIBLE_SENSITIVE_FIELDS = {
    "commission_rate_y1",
    "commission_rate_y2_plus",
    "discount_rate",
}

ALL_SENSITIVE_FIELDS = PARTNER_HIDDEN_FIELDS | PARTNER_VISIBLE_SENSITIVE_FIELDS


def filter_sensitive_fields(data: dict, current_user) -> dict:
    """
    Strip sensitive fields from a response dict based on user role.

    Args:
        data: response dict (e.g. ``model.__dict__`` or pydantic ``.model_dump()``)
        current_user: authenticated user from ``get_current_user``

    Returns:
        Dict with sensitive fields removed for partner-side roles.
        Internal roles receive the full dict unchanged.

    Usage:
        result = db.query(DealRegistration).first().__dict__
        return filter_sensitive_fields(result, current_user)
    """
    try:
        role = UserRole(current_user.role)
    except ValueError:
        return {k: v for k, v in data.items() if k not in PARTNER_HIDDEN_FIELDS}

    if role in PARTNER_ROLES:
        return {k: v for k, v in data.items() if k not in PARTNER_HIDDEN_FIELDS}

    return data


def is_field_visible(field_name: str, current_user) -> bool:
    """
    Check if a specific field is visible to the current user.
    Useful for conditional field inclusion in response schemas.
    """
    try:
        role = UserRole(current_user.role)
    except ValueError:
        return field_name not in PARTNER_HIDDEN_FIELDS

    if role in PARTNER_ROLES:
        return field_name not in PARTNER_HIDDEN_FIELDS

    return True
