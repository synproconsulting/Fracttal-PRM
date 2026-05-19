"""Sprint 11 / FPRM-179 — internal home dashboard summary.

    GET /internal/dashboard/summary   internal-JWT (system_admin,
                                                   channel_ops_admin,
                                                   channel_manager)

Returns a single roll-up that powers `InternalHome.jsx`:

    {
        "applications": {"pending_review": N,
                          "info_required": N,
                          "total_this_month": N},
        "deals":        {"submitted": N,
                          "under_review": N,
                          "approved_this_month": N,
                          "total_pipeline_value": float},
        "partners":     {"active": N, "pending_activation": N, "total": N},
        "conflicts":    {"open": N}
    }

All counts are read from existing tables — no new schema.
"""
from datetime import datetime
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import (
    ApplicationStatus,
    DealRegistration,
    PartnerApplication,
    PartnerOrganization,
    PartnerStatus,
    User,
)


router = APIRouter(prefix="/internal/dashboard", tags=["internal-dashboard"])


DASHBOARD_ROLES: Set[str] = {"system_admin", "channel_ops_admin", "channel_manager"}


def _require_dashboard_role(current_user: User) -> None:
    if current_user.role not in DASHBOARD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: internal dashboard requires system_admin, channel_ops_admin, or channel_manager",
        )


def _start_of_this_month() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


@router.get("/summary")
def get_internal_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_dashboard_role(current_user)

    month_start = _start_of_this_month()

    # --- Applications ---
    apps_pending_review = (
        db.query(func.count(PartnerApplication.id))
        .filter(PartnerApplication.status.in_([ApplicationStatus.submitted, ApplicationStatus.under_review]))
        .scalar()
        or 0
    )
    apps_info_required = (
        db.query(func.count(PartnerApplication.id))
        .filter(PartnerApplication.status == ApplicationStatus.info_required)
        .scalar()
        or 0
    )
    apps_total_this_month = (
        db.query(func.count(PartnerApplication.id))
        .filter(PartnerApplication.created_at >= month_start)
        .scalar()
        or 0
    )

    # --- Deals ---
    deals_submitted = (
        db.query(func.count(DealRegistration.id))
        .filter(DealRegistration.status == "submitted")
        .scalar()
        or 0
    )
    deals_under_review = (
        db.query(func.count(DealRegistration.id))
        .filter(DealRegistration.status == "under_review")
        .scalar()
        or 0
    )
    deals_approved_this_month = (
        db.query(func.count(DealRegistration.id))
        .filter(DealRegistration.status == "approved")
        .filter(DealRegistration.reviewed_at != None)  # noqa: E711
        .filter(DealRegistration.reviewed_at >= month_start)
        .scalar()
        or 0
    )
    deals_total_pipeline_value = (
        db.query(func.coalesce(func.sum(DealRegistration.estimated_deal_value), 0.0))
        .filter(DealRegistration.status.in_(["submitted", "under_review", "approved"]))
        .scalar()
        or 0.0
    )

    # --- Partners ---
    partners_active = (
        db.query(func.count(PartnerOrganization.id))
        .filter(PartnerOrganization.status == PartnerStatus.active)
        .scalar()
        or 0
    )
    partners_pending_activation = (
        db.query(func.count(PartnerOrganization.id))
        .filter(PartnerOrganization.status == PartnerStatus.applicant)
        .scalar()
        or 0
    )
    partners_total = db.query(func.count(PartnerOrganization.id)).scalar() or 0

    # --- Conflicts ---
    conflicts_open = (
        db.query(func.count(DealRegistration.id))
        .filter(DealRegistration.conflict_status == "conflict_detected")
        .scalar()
        or 0
    )

    return {
        "applications": {
            "pending_review": int(apps_pending_review),
            "info_required": int(apps_info_required),
            "total_this_month": int(apps_total_this_month),
        },
        "deals": {
            "submitted": int(deals_submitted),
            "under_review": int(deals_under_review),
            "approved_this_month": int(deals_approved_this_month),
            "total_pipeline_value": float(deals_total_pipeline_value),
        },
        "partners": {
            "active": int(partners_active),
            "pending_activation": int(partners_pending_activation),
            "total": int(partners_total),
        },
        "conflicts": {
            "open": int(conflicts_open),
        },
    }
