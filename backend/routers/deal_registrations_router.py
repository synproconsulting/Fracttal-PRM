"""Deal registration endpoints (Sprint 8 / FPRM-128).

Partner-facing endpoints:
    POST   /deal-registrations              partner_admin — create draft (activation-gated)
    GET    /deal-registrations              tenant-scoped — list deals
    GET    /deal-registrations/{id}         tenant-scoped — get one
    PATCH  /deal-registrations/{id}         partner_admin own + draft only — update
    POST   /deal-registrations/{id}/submit  partner_admin own — draft -> submitted, snapshot commission
    DELETE /deal-registrations/{id}         partner_admin own + draft only — delete draft

Activation gate: ``POST /deal-registrations`` requires
``partner_activation_checklists.activation_complete = True`` for the submitter's
org; otherwise returns 412 with `{detail, activation_url}`. The gate runs on
create only — drafts are allowed once a partner is fully active. Subsequent
submit/patch/delete operations are not re-gated.

Commission snapshot (on submit): resolves a row from ``commission_structures``
keyed by ``(partner_category_code, commission_type, year_1)`` and stores the id
+ percentage on the deal. If no row matches the deal's commission_type, the
snapshot fields stay null (the form's commission_type vocabulary is broader
than the commission_structures enum by design — Sprint 10's commission
visibility story will surface this to partners). See AD-14 for activation
recalc isolation — deal submission does not trigger activation recalc.

The internal review queue endpoints (`/internal/deals/*`) are added in
Story 5 / FPRM-134 in this same file.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from csv_export import csv_response
from conflict_checker import check_deal_conflict
from database import get_db
from models import (
    AuditLog,
    CommissionStructure,
    CommissionYear,
    DealMessage,
    DealRegistration,
    PartnerActivationChecklist,
    PartnerOrganization,
    PartnerStatus,
    User,
)
from approval_helpers import (
    WORKFLOW_DEAL_REGISTRATION,
    build_approval_progress,
    get_approval_step_context,
    record_step_action,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole


router = APIRouter(tags=["deal-registrations"])


CREATABLE_FIELDS = {
    # Phase 3 baseline (Sprint 8 / FPRM-128)
    "customer_name", "customer_domain", "customer_contact_name",
    "customer_contact_email", "customer_contact_phone", "customer_industry",
    "customer_country", "customer_region",
    "deal_name", "estimated_deal_value", "estimated_close_date",
    "deal_notes", "commission_type",
    # Sprint 20 / FPRM-316 -- Section A additional prospect/engagement fields
    "engagement_date", "prospect_phone", "compiled_by",
    "prospect_contact_name", "prospect_contact_position",
    "prospect_website", "industry_sector", "company_size",
    "feature_plan_preference",
    # Sprint 20 / FPRM-316 -- Section B Current State (Situation)
    "current_system", "old_system", "inventory_stores",
    "work_orders_prs", "monitoring_system",
    # Sprint 20 / FPRM-316 -- Section B Feature requirements
    "need_asset_depreciation", "need_wo_wr", "need_reports",
    "need_tool_management", "need_purchasing",
    "need_integration", "integration_with",
    "need_multi_language", "languages_required",
    "need_asset_management", "need_document_management",
    "need_cost_tracking", "need_monitoring",
    "need_schedule_third_parties", "need_track_labour",
    # Sprint 20 / FPRM-316 -- Section B SPICED narrative fields
    "about_client", "pain", "impact",
    "critical_event", "decision", "next_steps",
    # Post-Sprint 20 deal form fix -- requested license counts (migration 029)
    "qty_transactional_users", "qty_limited_tech_users",
    # NOTE: created_on_behalf_of is deliberately excluded here -- it is set
    # by the internal-create path (FPRM-317, Story 3) only, never by the
    # partner-facing POST/PATCH whitelist.
}


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# Date columns on DealRegistration. The frontend sends ISO strings; Postgres
# coerces them automatically but SQLite (used in tests) does not, so we parse
# them server-side. Unparseable values become None (no exception bubbled out).
_DATE_FIELDS = {"estimated_close_date", "engagement_date"}


def _coerce_dates(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    for k in _DATE_FIELDS:
        v = payload.get(k)
        if isinstance(v, str) and v:
            try:
                payload[k] = date.fromisoformat(v)
            except ValueError:
                payload[k] = None
    return payload


def _serialize(deal: DealRegistration) -> dict:
    return jsonable_encoder({c.name: getattr(deal, c.name) for c in deal.__table__.columns})


def _serialize_with_org(deal: DealRegistration, db: Session) -> dict:
    """Like _serialize, but adds ``partner_legal_name`` (FPRM-143).

    Used by the internal-facing endpoints so reviewers see the legal name of
    the partner org rather than its raw UUID.
    """
    base = _serialize(deal)
    legal_name = None
    if deal.partner_org_id is not None:
        org = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.id == deal.partner_org_id)
            .first()
        )
        legal_name = org.legal_name if org else None
    base["partner_legal_name"] = legal_name
    return base


def _bulk_org_names(db: Session, org_ids):
    """Return a dict {org_id: legal_name} for the given ids (one query)."""
    if not org_ids:
        return {}
    rows = (
        db.query(PartnerOrganization.id, PartnerOrganization.legal_name)
        .filter(PartnerOrganization.id.in_(list(org_ids)))
        .all()
    )
    return {str(rid): name for rid, name in rows}


def _require_partner_admin(user: User) -> None:
    if UserRole(user.role) != UserRole.partner_admin:
        raise HTTPException(
            status_code=403,
            detail="Only partner_admin can perform this action",
        )
    if user.partner_org_id is None:
        raise HTTPException(
            status_code=403,
            detail="Partner admin is not linked to an organisation",
        )


# FPRM-317 -- internal roles allowed to create deals on behalf of a partner.
_INTERNAL_CREATE_ROLES = {
    UserRole.channel_manager, UserRole.channel_ops_admin, UserRole.system_admin,
}

# Post-Sprint 20 PR B -- internal admin roles allowed to edit any deal in any
# status. Channel managers retain only their existing review actions; only
# system_admin and channel_ops_admin can correct deal data.
_INTERNAL_EDIT_ROLES = {
    UserRole.channel_ops_admin, UserRole.system_admin,
}


def _resolve_create_partner(user: User, payload: dict, db: Session):
    """Return (partner_org_id: uuid.UUID, on_behalf_of: bool) for POST.

    - partner_admin: uses ``user.partner_org_id`` (existing behaviour),
      on_behalf_of=False.
    - channel_manager / channel_ops_admin / system_admin: must pass
      ``partner_org_id`` in the request body. The org must exist and be
      ``PartnerStatus.active``. on_behalf_of=True.
    - All other roles: 403.
    """
    role = UserRole(user.role)
    if role == UserRole.partner_admin:
        _require_partner_admin(user)
        return user.partner_org_id, False
    if role in _INTERNAL_CREATE_ROLES:
        raw = payload.get("partner_org_id")
        if not raw:
            raise HTTPException(
                status_code=422,
                detail="partner_org_id is required when an internal user creates a deal",
            )
        try:
            pid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid partner_org_id")
        org = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.id == pid)
            .first()
        )
        if org is None:
            raise HTTPException(status_code=404, detail="Partner organisation not found")
        org_status = org.status.value if hasattr(org.status, "value") else org.status
        if org_status != PartnerStatus.active.value:
            raise HTTPException(
                status_code=422,
                detail=f"Partner organisation is not active (status={org_status})",
            )
        return pid, True
    raise HTTPException(
        status_code=403,
        detail="Permission denied: partner_admin or channel_manager+ required",
    )


def _enforce_tenant_read(user: User, deal: DealRegistration) -> None:
    role = UserRole(user.role)
    if role in PARTNER_ROLES:
        if user.partner_org_id is None or str(user.partner_org_id) != str(deal.partner_org_id):
            raise HTTPException(status_code=403, detail="Access denied")


def _get_deal_or_404(deal_id: uuid.UUID, db: Session) -> DealRegistration:
    deal = db.query(DealRegistration).filter(DealRegistration.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal registration not found")
    return deal


def _check_activation(db: Session, partner_org_id: uuid.UUID) -> None:
    """Activation gate per AD-14: deal create requires activation_complete=True.

    A missing checklist row is treated as not-activated. We do NOT call
    ``recalculate_activation`` here — deal-registration is downstream of
    activation, never upstream (AD-14 keeps recalc inside activation.py only).
    """
    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_org_id)
        .first()
    )
    if not checklist or not checklist.activation_complete:
        raise HTTPException(
            status_code=412,
            detail={
                "detail": "Partner activation incomplete",
                "activation_url": "/portal/home",
            },
        )


def _snapshot_commission(db: Session, deal: DealRegistration) -> None:
    """Resolve commission_structures row matching the deal + partner category.

    Best-effort: if the partner_organization is missing, or no matching row
    exists for the (partner_category_code, commission_type, year_1) tuple,
    leave commission_structure_id and commission_rate_snapshot as None. Never
    raise — a missing snapshot is acceptable and surfaces in the internal
    review queue as a blank commission.
    """
    if not deal.commission_type:
        return

    org = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == deal.partner_org_id)
        .first()
    )
    if org is None or org.partner_category is None:
        return
    code = org.partner_category.value if hasattr(org.partner_category, "value") else str(org.partner_category)

    row = (
        db.query(CommissionStructure)
        .filter(
            CommissionStructure.partner_category_code == code,
            CommissionStructure.commission_type == deal.commission_type,
            CommissionStructure.year == CommissionYear.year_1,
        )
        .first()
    )
    if row is None:
        return
    deal.commission_structure_id = row.id
    try:
        deal.commission_rate_snapshot = float(row.commission_pct)
    except (TypeError, ValueError):
        deal.commission_rate_snapshot = None


@router.post("/deal-registrations", status_code=201)
def create_deal(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new draft deal registration.

    Authorisation:
      * ``partner_admin`` -- existing path, activation-gated. ``partner_org_id``
        is taken from the JWT.
      * ``channel_manager`` / ``channel_ops_admin`` / ``system_admin`` --
        FPRM-317. Must supply ``partner_org_id`` in the body. The partner org
        must exist and be active. The deal is created with
        ``created_on_behalf_of=True``. The activation gate is **skipped** for
        internal-created deals -- the channel manager is responsible for the
        timing decision.
    """
    partner_org_id, on_behalf_of = _resolve_create_partner(current_user, payload, db)
    if not on_behalf_of:
        # Activation gate applies to partner-created deals only.
        _check_activation(db, partner_org_id)

    if not (payload.get("customer_name") or "").strip():
        raise HTTPException(status_code=422, detail="customer_name is required")
    if not (payload.get("deal_name") or "").strip():
        raise HTTPException(status_code=422, detail="deal_name is required")

    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status="draft",
        conflict_status="not_checked",
        created_on_behalf_of=on_behalf_of,
    )
    payload = _coerce_dates(payload)
    for key, value in payload.items():
        if key in CREATABLE_FIELDS:
            setattr(deal, key, value)
    db.add(deal)
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action=("deal_registration.created_internal" if on_behalf_of
                else "deal_registration.created"),
        object_type="deal_registration",
        object_id=deal.id,
        after={
            "status": deal.status,
            "deal_name": deal.deal_name,
            "partner_org_id": str(partner_org_id),
            "created_on_behalf_of": on_behalf_of,
        },
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.get("/deal-registrations")
def list_deals(
    status: Optional[str] = Query(default=None),
    partner_org_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    export: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List deals. partner roles see own org only; internal roles see all (filterable)."""
    role = UserRole(current_user.role)
    query = db.query(DealRegistration)

    if role in PARTNER_ROLES:
        if current_user.partner_org_id is None:
            return {"total": 0, "limit": limit, "offset": offset, "items": []}
        query = query.filter(DealRegistration.partner_org_id == current_user.partner_org_id)
    elif role in INTERNAL_ROLES:
        if partner_org_id is not None:
            query = query.filter(DealRegistration.partner_org_id == partner_org_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    if status:
        query = query.filter(DealRegistration.status == status)

    if export == "csv":
        rows_csv = (
            query.order_by(DealRegistration.created_at.desc()).all()
        )
        org_names = _bulk_org_names(db, {d.partner_org_id for d in rows_csv if d.partner_org_id})
        return csv_response(
            "deals_export",
            ["Deal Name", "Customer Domain", "Partner Org", "Deal Value",
             "Status", "Submitted Date", "Commission Type", "Commission Rate"],
            [
                [
                    d.deal_name or "",
                    d.customer_domain or "",
                    org_names.get(str(d.partner_org_id)) if d.partner_org_id else "",
                    float(d.estimated_deal_value) if d.estimated_deal_value is not None else "",
                    d.status or "",
                    d.submitted_at.date().isoformat() if d.submitted_at else "",
                    d.commission_type or "",
                    float(d.commission_rate_snapshot) if d.commission_rate_snapshot is not None else "",
                ]
                for d in rows_csv
            ],
        )

    total = query.count()
    items = (
        query.order_by(DealRegistration.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize(d) for d in items],
    }


@router.get("/deal-registrations/{deal_id}")
def get_deal(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = _get_deal_or_404(deal_id, db)
    _enforce_tenant_read(current_user, deal)
    # Include partner_legal_name for the internal detail page (FPRM-143).
    # Partner users see their own org so the field is still useful & not leaky.
    data = _serialize_with_org(deal, db)
    # FPRM-274 / Sprint 17 — surface multi-step approval state (None when no
    # workflow steps are configured for deal_registration).
    steps, _current, completed = get_approval_step_context(
        db, WORKFLOW_DEAL_REGISTRATION, deal.id,
    )
    data["approval_progress"] = build_approval_progress(steps, completed)
    return data


@router.patch("/deal-registrations/{deal_id}")
def update_deal(
    deal_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update deal fields.

    Authorisation:
      * ``partner_admin`` -- own org only, draft status only (unchanged).
      * ``system_admin`` / ``channel_ops_admin`` (post-Sprint 20 PR B) --
        any deal in any status. For these callers, every changed whitelisted
        field is logged as a ``deal.field_updated`` audit event with the
        old and new value so the deal detail's Change Log can reconstruct
        who edited what.
    """
    role = UserRole(current_user.role)
    is_internal_edit = role in _INTERNAL_EDIT_ROLES

    if not is_internal_edit:
        _require_partner_admin(current_user)

    deal = _get_deal_or_404(deal_id, db)

    if not is_internal_edit:
        if str(deal.partner_org_id) != str(current_user.partner_org_id):
            raise HTTPException(status_code=403, detail="Access denied")
        if deal.status != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit deal in status '{deal.status}'",
            )

    before = _serialize(deal)
    payload = _coerce_dates(payload)
    changed_fields = []
    for key, value in payload.items():
        if key not in CREATABLE_FIELDS:
            continue
        old_value = getattr(deal, key)
        # Skip no-op writes -- only audit / mutate when the value actually
        # changes. Compare via the JSON-serialised form so date/UUID/decimal
        # types compare equal to their wire representations.
        before_json = jsonable_encoder(old_value)
        after_json = jsonable_encoder(value)
        if before_json == after_json:
            continue
        setattr(deal, key, value)
        changed_fields.append((key, before_json, after_json))
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    ip = _client_ip(request)
    if is_internal_edit:
        # Per-field audit events so the Change Log can render a row per change.
        for field_name, old_v, new_v in changed_fields:
            log_audit_event(
                db=db,
                actor=current_user,
                action="deal.field_updated",
                object_type="deal_registration",
                object_id=deal.id,
                before={field_name: old_v},
                after={field_name: new_v},
                ip_address=ip,
            )
    else:
        log_audit_event(
            db=db,
            actor=current_user,
            action="deal_registration.updated",
            object_type="deal_registration",
            object_id=deal.id,
            before={"status": before["status"]},
            after={"status": deal.status},
            ip_address=ip,
        )
    return _serialize(deal)


@router.post("/deal-registrations/{deal_id}/submit")
def submit_deal(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a draft (or info_required) deal. Snapshots commission rate."""
    _require_partner_admin(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if str(deal.partner_org_id) != str(current_user.partner_org_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if deal.status not in ("draft", "info_required"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit deal in status '{deal.status}'",
        )
    if not (deal.customer_name or "").strip() or not (deal.deal_name or "").strip():
        raise HTTPException(
            status_code=422,
            detail="customer_name and deal_name are required to submit",
        )

    before_status = deal.status
    _snapshot_commission(db, deal)
    deal.status = "submitted"
    deal.submitted_at = datetime.utcnow()
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    # FPRM-157: run conflict check after the status flip so the deal being
    # submitted is not counted as a conflict against itself. The check is
    # best-effort — a checker exception must not roll back the submit.
    try:
        result = check_deal_conflict(db, deal.id)
        deal.conflict_status = result.conflict_status
        deal.conflict_checked_at = datetime.utcnow()
        deal.conflict_notes = result.notes
        db.commit()
        db.refresh(deal)
    except Exception:  # noqa: BLE001
        pass

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.submitted",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={
            "status": "submitted",
            "commission_structure_id": str(deal.commission_structure_id) if deal.commission_structure_id else None,
            "commission_rate_snapshot": deal.commission_rate_snapshot,
            "conflict_status": deal.conflict_status,
        },
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.delete("/deal-registrations/{deal_id}", status_code=204)
def delete_deal(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a draft. partner_admin own org only; draft status only."""
    _require_partner_admin(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if str(deal.partner_org_id) != str(current_user.partner_org_id):
        raise HTTPException(status_code=403, detail="Access denied")
    if deal.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete deal in status '{deal.status}'",
        )

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.deleted",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": "draft", "deal_name": deal.deal_name},
        ip_address=_client_ip(request),
    )
    db.delete(deal)
    db.commit()
    return None


# -------------------- Change log (post-Sprint 20 PR B) --------------------


@router.get("/internal/deals/{deal_id}/change-log")
def list_deal_change_log(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return every ``deal.field_updated`` audit event for this deal.

    Each event has ``before_state = {<field>: <old>}`` and
    ``after_state = {<field>: <new>}`` -- the response unpacks that pair into
    a flat ``field_name`` / ``old_value`` / ``new_value`` shape so the
    frontend's Change Log tab can render a simple row per change.

    Access: any internal role (channel_manager / channel_ops_admin /
    system_admin) -- only system_admin and channel_ops_admin can *produce*
    these events via PATCH, but channel_manager reviewers need read access
    to see corrections that landed before their review.
    """
    _require_review_role(current_user)
    _get_deal_or_404(deal_id, db)  # 404 if the deal doesn't exist

    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.object_type == "deal_registration",
            AuditLog.object_id == deal_id,
            AuditLog.action == "deal.field_updated",
        )
        .order_by(AuditLog.timestamp.desc())
        .all()
    )

    # Resolve actor email once per actor_id (cheap -- there are usually only
    # a handful of distinct editors per deal).
    actor_ids = {r.actor_id for r in rows if r.actor_id is not None}
    actor_emails = {}
    if actor_ids:
        for uid, email in (
            db.query(User.id, User.email)
            .filter(User.id.in_(list(actor_ids)))
            .all()
        ):
            actor_emails[str(uid)] = email

    out = []
    for r in rows:
        before = r.before_state or {}
        after = r.after_state or {}
        field_name = next(iter(after.keys()), next(iter(before.keys()), None))
        out.append({
            "id": str(r.id),
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "actor_id": str(r.actor_id) if r.actor_id else None,
            "actor_email": actor_emails.get(str(r.actor_id)) if r.actor_id else None,
            "actor_role": r.actor_role,
            "field_name": field_name,
            "old_value": before.get(field_name) if field_name else None,
            "new_value": after.get(field_name) if field_name else None,
        })
    return out


# -------------------- Internal deal review endpoints (Sprint 8 / FPRM-134) --------------------


REVIEW_ROLES = {UserRole.channel_manager, UserRole.system_admin, UserRole.channel_ops_admin}


def _require_review_role(user: User) -> None:
    if UserRole(user.role) not in REVIEW_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: review role required",
        )


@router.get("/internal/deals")
def list_internal_deals(
    status: Optional[str] = Query(default=None),
    partner_org_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    export: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Internal queue — channel_manager / channel_ops_admin / system_admin only.

    Supports `?status=` and `?partner_org_id=` filters. By default returns all
    statuses; the frontend filter tabs constrain to submitted / under_review.
    """
    _require_review_role(current_user)
    query = db.query(DealRegistration)
    if status:
        query = query.filter(DealRegistration.status == status)
    if partner_org_id is not None:
        query = query.filter(DealRegistration.partner_org_id == partner_org_id)

    if export == "csv":
        rows_csv = (
            query.order_by(DealRegistration.submitted_at.desc().nullslast(),
                           DealRegistration.created_at.desc()).all()
        )
        org_names = _bulk_org_names(db, {d.partner_org_id for d in rows_csv if d.partner_org_id})
        return csv_response(
            "deals_export",
            ["Deal Name", "Customer Domain", "Partner Org", "Deal Value",
             "Status", "Submitted Date", "Commission Type", "Commission Rate"],
            [
                [
                    d.deal_name or "",
                    d.customer_domain or "",
                    org_names.get(str(d.partner_org_id)) if d.partner_org_id else "",
                    float(d.estimated_deal_value) if d.estimated_deal_value is not None else "",
                    d.status or "",
                    d.submitted_at.date().isoformat() if d.submitted_at else "",
                    d.commission_type or "",
                    float(d.commission_rate_snapshot) if d.commission_rate_snapshot is not None else "",
                ]
                for d in rows_csv
            ],
        )

    total = query.count()
    items = (
        query.order_by(DealRegistration.submitted_at.desc().nullslast(), DealRegistration.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # FPRM-143: include partner_legal_name on each row (bulk lookup, single query).
    name_map = _bulk_org_names(db, {d.partner_org_id for d in items if d.partner_org_id})
    rows = []
    for d in items:
        body = _serialize(d)
        body["partner_legal_name"] = name_map.get(str(d.partner_org_id)) if d.partner_org_id else None
        rows.append(body)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.post("/internal/deals/{deal_id}/start-review")
def start_review(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """submitted -> under_review. Records the reviewer."""
    _require_review_role(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if deal.status != "submitted":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start review of deal in status '{deal.status}'",
        )

    deal.status = "under_review"
    deal.reviewer_id = current_user.id
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.review_started",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": "submitted"},
        after={"status": "under_review"},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.post("/internal/deals/{deal_id}/approve")
def approve_deal(
    deal_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """under_review -> approved. Requires review_notes.

    FPRM-274 / Sprint 17 — when ``approval_workflow_steps`` defines multiple
    steps for ``deal_registration``, each step must be approved by a user
    whose role matches the step's ``required_role``. Intermediate-step
    approvals stamp an ``ApprovalStepRecord`` and return ``approval_progress``
    without changing the deal status. If no steps are configured, single-step
    legacy behaviour is preserved.
    """
    _require_review_role(current_user)
    review_notes = (payload.get("review_notes") or "").strip() if payload else ""
    if not review_notes:
        raise HTTPException(status_code=422, detail="review_notes is required")

    deal = _get_deal_or_404(deal_id, db)
    if deal.status != "under_review":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve deal in status '{deal.status}'",
        )

    steps, current_step, completed_count = get_approval_step_context(
        db, WORKFLOW_DEAL_REGISTRATION, deal.id,
    )

    if steps:
        if current_step is None:
            raise HTTPException(
                status_code=422,
                detail="All approval steps are already completed",
            )
        if current_user.role != current_step.required_role:
            raise HTTPException(
                status_code=403,
                detail=f"This step requires role: {current_step.required_role}",
            )

        record_step_action(
            db,
            workflow_type=WORKFLOW_DEAL_REGISTRATION,
            object_id=deal.id,
            step=current_step,
            actor_id=current_user.id,
            action="approved",
            notes=review_notes,
        )

        is_final_step = (completed_count + 1) >= len(steps)

        if not is_final_step:
            db.commit()
            db.refresh(deal)
            log_audit_event(
                db=db,
                actor=current_user,
                action="deal_registration.step_approved",
                object_type="deal_registration",
                object_id=deal.id,
                before={"status": deal.status},
                after={
                    "step_order": current_step.step_order,
                    "step_name": current_step.step_name,
                    "completed_steps": completed_count + 1,
                    "total_steps": len(steps),
                },
                ip_address=_client_ip(request),
            )
            data = _serialize(deal)
            data["approval_progress"] = build_approval_progress(steps, completed_count + 1)
            data["message"] = (
                f"Step {current_step.step_order} of {len(steps)} approved. "
                "Awaiting next step."
            )
            return data
        # Final step — fall through to the existing approval flow.

    before_status = deal.status
    deal.status = "approved"
    deal.review_notes = review_notes
    deal.reviewer_id = current_user.id
    deal.reviewed_at = datetime.utcnow()
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.approved",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={"status": "approved", "review_notes": review_notes},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.post("/internal/deals/{deal_id}/reject")
def reject_deal(
    deal_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """under_review -> rejected. Requires review_notes."""
    _require_review_role(current_user)
    review_notes = (payload.get("review_notes") or "").strip() if payload else ""
    if not review_notes:
        raise HTTPException(status_code=422, detail="review_notes is required")

    deal = _get_deal_or_404(deal_id, db)
    if deal.status != "under_review":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject deal in status '{deal.status}'",
        )

    # FPRM-274 / Sprint 17 — snapshot the current step so the audit trail
    # shows which step terminated the workflow.
    steps, current_step, _completed = get_approval_step_context(
        db, WORKFLOW_DEAL_REGISTRATION, deal.id,
    )
    if steps and current_step is not None:
        record_step_action(
            db,
            workflow_type=WORKFLOW_DEAL_REGISTRATION,
            object_id=deal.id,
            step=current_step,
            actor_id=current_user.id,
            action="rejected",
            notes=review_notes,
        )

    before_status = deal.status
    deal.status = "rejected"
    deal.review_notes = review_notes
    deal.reviewer_id = current_user.id
    deal.reviewed_at = datetime.utcnow()
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.rejected",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={"status": "rejected", "review_notes": review_notes},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


# -------------------- Conflict override (Sprint 10 / FPRM-157) --------------------


OVERRIDE_ROLES = {UserRole.channel_manager, UserRole.system_admin}


@router.post("/internal/deals/{deal_id}/override-conflict")
def override_conflict(
    deal_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a conflict_detected deal as ``clear`` after a manual review.

    Access: ``channel_manager`` + ``system_admin`` only — channel_ops_admin and
    review-only roles cannot override. Body requires ``override_notes`` (a
    free-text rationale appended to ``conflict_notes`` for the audit trail).
    """
    if UserRole(current_user.role) not in OVERRIDE_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: override role required",
        )
    override_notes = (payload.get("override_notes") or "").strip() if payload else ""
    if not override_notes:
        raise HTTPException(status_code=422, detail="override_notes is required")

    deal = _get_deal_or_404(deal_id, db)
    before_status = deal.conflict_status
    before_notes = deal.conflict_notes
    deal.conflict_status = "clear"
    appended = (
        f"{before_notes}\n\n[OVERRIDE by {current_user.email}]: {override_notes}"
        if before_notes
        else f"[OVERRIDE by {current_user.email}]: {override_notes}"
    )
    deal.conflict_notes = appended
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.conflict_overridden",
        object_type="deal_registration",
        object_id=deal.id,
        before={"conflict_status": before_status},
        after={"conflict_status": "clear", "override_notes": override_notes},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


# -------------------- Collaboration thread + request-info (Sprint 9 / FPRM-139) --------------------


def _serialize_message(msg: DealMessage) -> dict:
    return jsonable_encoder({
        "id": msg.id,
        "deal_id": msg.deal_id,
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "sender_email": msg.sender_email,
        "message": msg.message,
        "created_at": msg.created_at,
    })


def _resolve_sender_type(user: User) -> str:
    role = UserRole(user.role)
    if role in PARTNER_ROLES:
        return "partner"
    if role in INTERNAL_ROLES:
        return "internal"
    raise HTTPException(status_code=403, detail="Access denied")


@router.get("/deal-registrations/{deal_id}/messages")
def list_deal_messages(
    deal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the chronological collaboration thread for a deal.

    Access: partner roles see own org only (403 on cross-org), internal roles
    see any deal. Both partner and internal sides share the same thread view.
    """
    deal = _get_deal_or_404(deal_id, db)
    _enforce_tenant_read(current_user, deal)
    msgs = (
        db.query(DealMessage)
        .filter(DealMessage.deal_id == deal.id)
        .order_by(DealMessage.created_at.asc())
        .all()
    )
    return [_serialize_message(m) for m in msgs]


@router.post("/deal-registrations/{deal_id}/messages", status_code=201)
def post_deal_message(
    deal_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Append a message to the deal's collaboration thread.

    Access: partner roles 403 on other orgs' deals; internal roles always
    allowed. ``sender_type`` is derived from the caller's role.
    """
    deal = _get_deal_or_404(deal_id, db)
    _enforce_tenant_read(current_user, deal)
    sender_type = _resolve_sender_type(current_user)

    message_text = (payload.get("message") or "").strip() if payload else ""
    if not message_text:
        raise HTTPException(status_code=422, detail="message is required")

    msg = DealMessage(
        id=uuid.uuid4(),
        deal_id=deal.id,
        sender_type=sender_type,
        sender_id=current_user.id,
        sender_email=current_user.email,
        message=message_text,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.message_posted",
        object_type="deal_registration",
        object_id=deal.id,
        after={"sender_type": sender_type, "message_id": str(msg.id)},
        ip_address=_client_ip(request),
    )
    return _serialize_message(msg)


@router.post("/internal/deals/{deal_id}/request-info")
def request_info(
    deal_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """under_review -> info_required. Posts the reviewer note to the thread."""
    _require_review_role(current_user)
    message_text = (payload.get("message") or "").strip() if payload else ""
    if not message_text:
        raise HTTPException(status_code=422, detail="message is required")

    deal = _get_deal_or_404(deal_id, db)
    if deal.status != "under_review":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request info on deal in status '{deal.status}'",
        )

    before_status = deal.status
    deal.status = "info_required"
    deal.reviewer_id = current_user.id
    deal.updated_at = datetime.utcnow()

    msg = DealMessage(
        id=uuid.uuid4(),
        deal_id=deal.id,
        sender_type="internal",
        sender_id=current_user.id,
        sender_email=current_user.email,
        message=message_text,
    )
    db.add(msg)
    db.commit()
    db.refresh(deal)
    db.refresh(msg)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.info_required",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={"status": "info_required", "message_id": str(msg.id)},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)


@router.post("/internal/deals/{deal_id}/cancel-info-request")
def cancel_info_request(
    deal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sprint 11 / FPRM-186 — reverse an outstanding info request on a deal.

    info_required -> under_review. Posts a system message to the deal thread
    so the partner has a thread-level record that the request was cancelled.
    Allowed roles: channel_manager, channel_ops_admin, system_admin.
    """
    _require_review_role(current_user)
    deal = _get_deal_or_404(deal_id, db)
    if deal.status != "info_required":
        raise HTTPException(
            status_code=400,
            detail="Deal is not in info_required status",
        )

    before_status = deal.status
    deal.status = "under_review"
    deal.reviewer_id = current_user.id
    deal.updated_at = datetime.utcnow()

    system_message = DealMessage(
        id=uuid.uuid4(),
        deal_id=deal.id,
        sender_type="internal",
        sender_id=current_user.id,
        sender_email=current_user.email,
        message="Info request cancelled by reviewer.",
    )
    db.add(system_message)
    db.commit()
    db.refresh(deal)
    db.refresh(system_message)

    log_audit_event(
        db=db,
        actor=current_user,
        action="deal_registration.info_request_cancelled",
        object_type="deal_registration",
        object_id=deal.id,
        before={"status": before_status},
        after={"status": "under_review", "message_id": str(system_message.id)},
        ip_address=_client_ip(request),
    )
    return _serialize(deal)
