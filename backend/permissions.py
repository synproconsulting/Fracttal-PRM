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
from sqlalchemy import false as _sql_false

from auth import get_current_user
from models import PartnerChannelManager, User
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
        # AD-35 (FPRM-389): partner roles may mark their own-org quote
        # accepted (and attach proof). No create/edit/submit/retract/delete.
        "quote:accept_own",
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
        # AD-35 (FPRM-389): partner_admin may mark their own-org quote
        # accepted (and attach proof). No retract/delete.
        "quote:accept_own",
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


# ==========================================================================
# Channel-manager <-> partner approval routing (Sprint 24 PR B / FPRM-423 / AD-41)
#
# A SINGLE shared seam. These helpers sit AFTER each existing role guard and
# narrow only the ``channel_manager`` role to its assigned partners. They do
# NOT replace or modify any existing guard (that is the deferred Phase 7
# Dynamic RBAC work). Global fallback: while NO partner has any assignment,
# every channel_manager sees/acts on all partners (bootstrap). ``system_admin``
# and ``channel_ops_admin`` are ALWAYS unscoped.
# ==========================================================================

# Sentinel returned by ``resolve_cm_scope`` meaning "unscoped — sees everything".
ALL_PARTNERS = object()


def get_all_channel_managers(db):
    """All active users with the ``channel_manager`` role (notification/fallback set)."""
    return (
        db.query(User)
        .filter(User.role == UserRole.channel_manager.value, User.is_active.is_(True))
        .all()
    )


def get_assigned_partner_ids(db, user_id) -> set:
    """The set of partner_org_ids assigned to ``user_id``."""
    rows = (
        db.query(PartnerChannelManager.partner_org_id)
        .filter(PartnerChannelManager.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}


def assignments_exist(db, request=None) -> bool:
    """True if ANY assignment row exists anywhere — the global switch.

    This flips every channel_manager from "see all" to scoped the moment the
    first assignment is created. Cached per-request on ``request.state`` when a
    Request is supplied so it runs once, never per row.
    """
    if request is not None and hasattr(request, "state"):
        cached = getattr(request.state, "_cm_assignments_exist", None)
        if cached is not None:
            return cached
    exists = db.query(PartnerChannelManager.id).first() is not None
    if request is not None and hasattr(request, "state"):
        request.state._cm_assignments_exist = exists
    return exists


def resolve_cm_scope(db, user, request=None):
    """Resolve a user's partner scope for partner-scoped approval surfaces.

    Returns ``ALL_PARTNERS`` (unscoped) or a ``set`` of partner_org_ids:
      * system_admin / channel_ops_admin (and any non-channel_manager role) -> ALL_PARTNERS, always.
      * channel_manager -> ALL_PARTNERS if no assignments exist anywhere
        (bootstrap); otherwise the user's assigned id set (may be EMPTY -> sees
        / acts on nothing).
    """
    if UserRole(user.role) != UserRole.channel_manager:
        return ALL_PARTNERS
    if not assignments_exist(db, request):
        return ALL_PARTNERS
    return get_assigned_partner_ids(db, user.id)


def apply_cm_scope_to_query(query, db, user, partner_org_id_column, request=None):
    """Filter a queue query to the channel_manager's assigned partners.

    No-op for unscoped users; an empty assigned set yields zero rows.
    """
    scope = resolve_cm_scope(db, user, request)
    if scope is ALL_PARTNERS:
        return query
    if not scope:
        return query.filter(_sql_false())
    return query.filter(partner_org_id_column.in_(scope))


def cm_scope_label(db, user, request=None):
    """UI hint for the queue indicator (FPRM-425). Returns:
      * ``"assigned"`` -- channel_manager, assignments exist (queue is scoped).
      * ``"all"``      -- channel_manager, bootstrap (sees all partners).
      * ``None``       -- any other role (no indicator).
    """
    if UserRole(user.role) != UserRole.channel_manager:
        return None
    return "assigned" if assignments_exist(db, request) else "all"


def enforce_cm_scope(db, user, partner_org_id, request=None) -> None:
    """403 if a scoped channel_manager targets a partner outside their scope.

    No-op for unscoped users (admins, or any CM while in global-fallback).
    """
    scope = resolve_cm_scope(db, user, request)
    if scope is ALL_PARTNERS:
        return
    if partner_org_id is None or partner_org_id not in scope:
        raise HTTPException(
            status_code=403,
            detail="This partner is not assigned to you.",
        )
