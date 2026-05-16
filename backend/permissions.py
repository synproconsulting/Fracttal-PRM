"""
Permission matrix and RBAC enforcement for Fracttal PRM.

Permission strings follow the pattern: {resource}:{action}

Resources: partner_organization, partner_profile, partner_user,
           deal_registration, quote, training, asset, report,
           user_management, system_config

Actions: create, read_own, read_all, update_own, update_all,
         delete, approve, reject, export
"""
from fastapi import Depends, HTTPException, status

from auth import get_current_user
from roles import UserRole, PARTNER_ROLES


PERMISSIONS: dict[str, set[str]] = {

    UserRole.partner_user: {
        "partner_organization:read_own",
        "partner_profile:read_own",
        "deal_registration:create",
        "deal_registration:read_own",
        "deal_registration:update_own",
        "training:read_own",
        "asset:read_own",
        "quote:read_own",
    },

    UserRole.partner_admin: {
        "partner_organization:read_own",
        "partner_organization:update_own",
        "partner_profile:read_own",
        "partner_profile:update_own",
        "partner_user:create",
        "partner_user:read_own",
        "partner_user:update_own",
        "partner_user:delete",
        "deal_registration:create",
        "deal_registration:read_own",
        "deal_registration:update_own",
        "training:read_own",
        "asset:read_own",
        "quote:create",
        "quote:read_own",
        "quote:update_own",
        "report:read_own",
        "report:export",
    },

    UserRole.channel_manager: {
        "partner_organization:read_all",
        "partner_organization:update_all",
        "partner_profile:read_all",
        "partner_profile:update_all",
        "partner_user:read_all",
        "partner_application:read_all",
        "deal_registration:read_all",
        "deal_registration:update_all",
        "deal_registration:approve",
        "deal_registration:reject",
        "quote:read_all",
        "quote:approve",
        "quote:reject",
        "training:read_own",
        "asset:read_all",
        "report:read_all",
        "report:export",
    },

    UserRole.channel_ops_admin: {
        "partner_organization:create",
        "partner_organization:read_all",
        "partner_organization:update_all",
        "partner_organization:delete",
        "partner_profile:read_all",
        "partner_profile:update_all",
        "partner_user:create",
        "partner_user:read_all",
        "partner_user:update_all",
        "partner_user:delete",
        "partner_application:read_all",
        "partner_application:update_all",
        "deal_registration:read_all",
        "deal_registration:update_all",
        "deal_registration:approve",
        "deal_registration:reject",
        "quote:read_all",
        "quote:update_all",
        "quote:approve",
        "quote:reject",
        "training:create",
        "training:read_all",
        "training:update_all",
        "training:delete",
        "asset:create",
        "asset:read_all",
        "asset:update_all",
        "asset:delete",
        "report:read_all",
        "report:export",
        "system_config:read_all",
        "system_config:update_all",
    },

    UserRole.sales_rep: {
        "partner_organization:read_all",
        "partner_profile:read_all",
        "deal_registration:read_all",
        "deal_registration:update_all",
        "quote:read_all",
        "report:read_all",
        "report:export",
    },

    UserRole.sales_ops: {
        "partner_organization:read_all",
        "partner_profile:read_all",
        "deal_registration:read_all",
        "quote:create",
        "quote:read_all",
        "quote:update_all",
        "quote:approve",
        "quote:reject",
        "quote:export",
        "report:read_all",
        "report:export",
        "system_config:read_all",
        "system_config:update_all",
    },

    UserRole.finance_approver: {
        "partner_organization:read_all",
        "deal_registration:read_all",
        "quote:read_all",
        "quote:approve",
        "quote:reject",
        "report:read_all",
        "report:export",
    },

    UserRole.system_admin: {
        "partner_organization:create",
        "partner_organization:read_all",
        "partner_organization:update_all",
        "partner_organization:delete",
        "partner_profile:read_all",
        "partner_profile:update_all",
        "partner_user:create",
        "partner_user:read_all",
        "partner_user:update_all",
        "partner_user:delete",
        "partner_application:read_all",
        "partner_application:update_all",
        "deal_registration:create",
        "deal_registration:read_all",
        "deal_registration:update_all",
        "deal_registration:approve",
        "deal_registration:reject",
        "deal_registration:delete",
        "quote:create",
        "quote:read_all",
        "quote:update_all",
        "quote:approve",
        "quote:reject",
        "quote:delete",
        "quote:export",
        "training:create",
        "training:read_all",
        "training:update_all",
        "training:delete",
        "asset:create",
        "asset:read_all",
        "asset:update_all",
        "asset:delete",
        "report:read_all",
        "report:export",
        "user_management:create",
        "user_management:read_all",
        "user_management:update_all",
        "user_management:delete",
        "system_config:read_all",
        "system_config:update_all",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in PERMISSIONS.get(role, set())


def require_permission(permission: str):
    """
    FastAPI dependency factory for RBAC enforcement.

    Usage:
        @router.get("/resource")
        def get_resource(current_user = Depends(require_permission("resource:read_all"))):
            ...

    Returns 403 if the authenticated user's role lacks the permission.
    """
    def checker(current_user=Depends(get_current_user)):
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        return current_user
    return checker


def get_partner_org_filter(current_user) -> dict:
    """
    Return SQLAlchemy filter kwargs to enforce tenant isolation.

    For partner-side roles: ``{"partner_org_id": current_user.partner_org_id}``
    For internal roles:     ``{}`` (no filter; sees all)

    Usage:
        filters = get_partner_org_filter(current_user)
        query = db.query(Model).filter_by(**filters)
    """
    if UserRole(current_user.role) in PARTNER_ROLES:
        return {"partner_org_id": current_user.partner_org_id}
    return {}


def apply_tenant_filter(query, current_user, model):
    """
    Apply tenant isolation to a SQLAlchemy query.

    Args:
        query: active SQLAlchemy query
        current_user: authenticated user from ``get_current_user``
        model: SQLAlchemy model being queried (must have ``partner_org_id`` column)

    Usage:
        query = db.query(PartnerOrganization)
        query = apply_tenant_filter(query, current_user, PartnerOrganization)
        results = query.all()
    """
    if UserRole(current_user.role) in PARTNER_ROLES:
        return query.filter(model.partner_org_id == current_user.partner_org_id)
    return query
