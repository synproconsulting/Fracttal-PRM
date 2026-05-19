"""Sprint 14 / FPRM-221 — internal reporting endpoints.

All aggregations are computed at query time from existing tables; no
pre-aggregated reporting tables exist (AD-17). Acceptable at current data
volumes (single-digit thousands of deals). If volumes ever exceed ~50k deals
revisit with a nightly rollup table.

Endpoints exposed under ``/internal/reports``:

    GET  /pipeline               — partner / category / tier roll-up + totals
    GET  /cycle-times            — submitted -> reviewed days, all-time
    GET  /conflicts              — conflict rate + unresolved list
    GET  /partner-activity       — per-partner last-deal + 90d count
    GET  /pipeline/export        — CSV (Authorization-protected download)

Role gating:
    /pipeline, /cycle-times, /conflicts, /partner-activity →
        system_admin, channel_ops_admin, channel_manager, sales_ops
    /pipeline/export additionally permits finance_approver (finance pulls CSVs
        of approved deals for commission reconciliation).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import (
    DealRegistration,
    PartnerActivationChecklist,
    PartnerApplication,
    PartnerApplicationDocument,
    PartnerOrganization,
    User,
)

router = APIRouter(prefix="/internal/reports", tags=["reports"])


REPORT_ROLES: Set[str] = {"system_admin", "channel_ops_admin", "channel_manager", "sales_ops"}
EXPORT_ROLES: Set[str] = REPORT_ROLES | {"finance_approver"}


def _require_report_role(current_user: User) -> None:
    if current_user.role not in REPORT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: reports require system_admin, channel_ops_admin, channel_manager, or sales_ops",
        )


def _require_export_role(current_user: User) -> None:
    if current_user.role not in EXPORT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: export requires system_admin, channel_ops_admin, channel_manager, sales_ops, or finance_approver",
        )


def _parse_iso_date(value: Optional[str], field_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be ISO date (YYYY-MM-DD)",
        ) from exc


def _enum_value(v) -> str:
    return getattr(v, "value", v) if v is not None else ""


def _filtered_deals_with_orgs(
    db: Session,
    from_date: Optional[date],
    to_date: Optional[date],
    partner_category: Optional[str],
    tier: Optional[str],
):
    """Return list of (deal, org) tuples matching the optional filters."""
    query = (
        db.query(DealRegistration, PartnerOrganization)
        .join(PartnerOrganization, PartnerOrganization.id == DealRegistration.partner_org_id)
    )
    if from_date is not None:
        query = query.filter(DealRegistration.submitted_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        # to_date inclusive — include everything up to end of that day
        query = query.filter(DealRegistration.submitted_at <= datetime.combine(to_date, datetime.max.time()))
    rows = query.all()

    if partner_category:
        rows = [(d, o) for (d, o) in rows if _enum_value(o.partner_category) == partner_category]
    if tier:
        rows = [(d, o) for (d, o) in rows if _enum_value(o.tier) == tier]
    return rows


@router.get("/pipeline")
def get_pipeline_report(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    partner_category: Optional[str] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_report_role(current_user)
    fd = _parse_iso_date(from_date, "from_date")
    td = _parse_iso_date(to_date, "to_date")

    rows = _filtered_deals_with_orgs(db, fd, td, partner_category, tier)

    by_partner_map: dict = {}
    by_category_map: dict = {}
    by_tier_map: dict = {}
    totals = {
        "total_deals": 0,
        "approved": 0,
        "rejected": 0,
        "under_review": 0,
        "total_value": 0.0,
    }

    for deal, org in rows:
        category = _enum_value(org.partner_category)
        tier_val = _enum_value(org.tier) or "Unassigned"
        value = float(deal.estimated_deal_value or 0.0)
        status_val = deal.status or ""

        # by_partner
        bp = by_partner_map.setdefault(
            str(org.id),
            {"partner_name": org.legal_name, "org_id": str(org.id), "total_deals": 0, "approved": 0, "total_value": 0.0},
        )
        bp["total_deals"] += 1
        if status_val == "approved":
            bp["approved"] += 1
        bp["total_value"] += value

        # by_category
        bc = by_category_map.setdefault(category, {"category": category, "total_deals": 0, "approved": 0})
        bc["total_deals"] += 1
        if status_val == "approved":
            bc["approved"] += 1

        # by_tier
        bt = by_tier_map.setdefault(tier_val, {"tier": tier_val, "total_deals": 0})
        bt["total_deals"] += 1

        # totals
        totals["total_deals"] += 1
        if status_val == "approved":
            totals["approved"] += 1
        elif status_val == "rejected":
            totals["rejected"] += 1
        elif status_val == "under_review":
            totals["under_review"] += 1
        totals["total_value"] += value

    return {
        "by_partner": list(by_partner_map.values()),
        "by_category": list(by_category_map.values()),
        "by_tier": list(by_tier_map.values()),
        "totals": totals,
    }


@router.get("/cycle-times")
def get_cycle_times_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_report_role(current_user)

    rows = (
        db.query(DealRegistration, PartnerOrganization)
        .join(PartnerOrganization, PartnerOrganization.id == DealRegistration.partner_org_id)
        .all()
    )

    completed = [
        (deal, org)
        for (deal, org) in rows
        if deal.reviewed_at is not None and deal.submitted_at is not None
    ]
    cycle_days_list = [
        (deal, org, (deal.reviewed_at - deal.submitted_at).total_seconds() / 86400.0)
        for (deal, org) in completed
    ]

    overall_avg_days = (
        sum(d for (_, _, d) in cycle_days_list) / len(cycle_days_list)
        if cycle_days_list
        else None
    )

    # Group by (category, YYYY-MM of submitted_at)
    bucket_map: dict = {}
    for (deal, org, days) in cycle_days_list:
        category = _enum_value(org.partner_category)
        month = deal.submitted_at.strftime("%Y-%m")
        key = (category, month)
        bucket = bucket_map.setdefault(key, {"category": category, "month": month, "_sum": 0.0, "deal_count": 0})
        bucket["_sum"] += days
        bucket["deal_count"] += 1

    by_category_and_month = []
    for bucket in bucket_map.values():
        by_category_and_month.append(
            {
                "category": bucket["category"],
                "month": bucket["month"],
                "avg_days": round(bucket["_sum"] / bucket["deal_count"], 2),
                "deal_count": bucket["deal_count"],
            }
        )
    by_category_and_month.sort(key=lambda x: (x["month"], x["category"]))

    # slowest_deals: filter approved/rejected, sort by cycle desc, top 5
    decided = [
        (deal, org, days)
        for (deal, org, days) in cycle_days_list
        if (deal.status or "") in ("approved", "rejected")
    ]
    decided.sort(key=lambda t: t[2], reverse=True)
    slowest_deals = [
        {
            "deal_id": str(deal.id),
            "deal_name": deal.deal_name,
            "partner_name": org.legal_name,
            "days_to_decision": round(days, 2),
            "status": deal.status,
        }
        for (deal, org, days) in decided[:5]
    ]

    return {
        "overall_avg_days": (round(overall_avg_days, 2) if overall_avg_days is not None else None),
        "by_category_and_month": by_category_and_month,
        "slowest_deals": slowest_deals,
    }


@router.get("/conflicts")
def get_conflicts_report(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    partner_category: Optional[str] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_report_role(current_user)
    fd = _parse_iso_date(from_date, "from_date")
    td = _parse_iso_date(to_date, "to_date")

    rows = _filtered_deals_with_orgs(db, fd, td, partner_category, tier)

    total_deals = len(rows)
    conflict_rows = [(d, o) for (d, o) in rows if (d.conflict_status or "") == "conflict_detected"]
    conflict_count = len(conflict_rows)
    conflict_rate_pct = (
        round(conflict_count / total_deals * 100, 1) if total_deals > 0 else 0.0
    )

    unresolved = [
        (d, o)
        for (d, o) in conflict_rows
        if (d.status or "") not in ("approved", "rejected")
    ]
    unresolved.sort(key=lambda t: t[0].submitted_at or datetime.min, reverse=True)

    unresolved_conflicts = [
        {
            "deal_id": str(d.id),
            "deal_name": d.deal_name,
            "partner_name": o.legal_name,
            "customer_domain": d.customer_domain,
            "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        }
        for (d, o) in unresolved
    ]

    return {
        "total_deals": total_deals,
        "conflict_count": conflict_count,
        "conflict_rate_pct": conflict_rate_pct,
        "unresolved_conflicts": unresolved_conflicts,
    }


@router.get("/partner-activity")
def get_partner_activity_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_report_role(current_user)

    now = datetime.utcnow()
    cutoff = now - timedelta(days=90)

    active_orgs = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.status == "active")
        .all()
    )

    partners = []
    for org in active_orgs:
        deals = (
            db.query(DealRegistration)
            .filter(DealRegistration.partner_org_id == org.id)
            .all()
        )
        submitted_dates = [d.submitted_at for d in deals if d.submitted_at]
        last_deal_submitted = max(submitted_dates).isoformat() if submitted_dates else None
        deals_last_90_days = sum(1 for sd in submitted_dates if sd >= cutoff)

        checklist = (
            db.query(PartnerActivationChecklist)
            .filter(PartnerActivationChecklist.partner_org_id == org.id)
            .first()
        )
        activation_complete = bool(checklist.activation_complete) if checklist else False

        # Documents are uploaded against PartnerApplication; join via partner_org_id
        document_count = (
            db.query(PartnerApplicationDocument)
            .join(
                PartnerApplication,
                PartnerApplication.id == PartnerApplicationDocument.application_id,
            )
            .filter(PartnerApplication.partner_org_id == org.id)
            .count()
        )

        partners.append(
            {
                "org_id": str(org.id),
                "legal_name": org.legal_name,
                "last_deal_submitted": last_deal_submitted,
                "deals_last_90_days": deals_last_90_days,
                "activation_complete": activation_complete,
                "document_count": int(document_count),
            }
        )

    return {"partners": partners}


@router.get("/pipeline/export")
def export_pipeline_csv(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    partner_category: Optional[str] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_export_role(current_user)
    fd = _parse_iso_date(from_date, "from_date")
    td = _parse_iso_date(to_date, "to_date")

    rows = _filtered_deals_with_orgs(db, fd, td, partner_category, tier)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Partner Name", "Category", "Tier", "Deal Name", "Customer Name",
        "Deal Value", "Status", "Submitted Date", "Approved Date", "Commission Rate",
    ])
    for deal, org in rows:
        approved_date = (
            deal.reviewed_at.isoformat()
            if deal.status == "approved" and deal.reviewed_at is not None
            else ""
        )
        writer.writerow([
            org.legal_name or "",
            _enum_value(org.partner_category) or "",
            _enum_value(org.tier) or "",
            deal.deal_name or "",
            deal.customer_name or "",
            "" if deal.estimated_deal_value is None else str(deal.estimated_deal_value),
            deal.status or "",
            deal.submitted_at.isoformat() if deal.submitted_at else "",
            approved_date,
            "" if deal.commission_rate_snapshot is None else str(deal.commission_rate_snapshot),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pipeline_export.csv"},
    )
