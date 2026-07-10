"""Partner organization CRUD endpoints + activation checklist endpoints.

Permissions:
    GET    /partners                                  - partner_organization:read_all (internal)
    GET    /partners/{id}                             - any authenticated (partner-side limited to own org)
    POST   /partners                                  - partner_organization:create (channel_ops_admin, system_admin)
    PATCH  /partners/{id}                             - channel_ops_admin/system_admin (any) or partner_admin (own org)
    GET    /partners/{id}/activation                  - partner_admin (own org) or any internal role
    POST   /partners/{id}/activation/recalculate      - channel_manager / channel_ops_admin / system_admin

Sprint 7 / FPRM-107 - activation endpoints. PATCH /partners/{id} now also
calls recalculate_activation in case contract_start_date was touched (the
terms_signed flag depends on it).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from sqlalchemy import func

from models import (
    ActivationChecklistConfig,
    CommissionStructure,
    DealRegistration,
    DocumentStatus,
    PartnerActivationChecklist,
    PartnerDocument,
    PartnerOrganization,
    PartnerProfile,
    Quote,
    QuoteVersion,
    User,
)
from permissions import require_permission, enforce_cm_scope
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partners"])


def _serialize(partner: PartnerOrganization) -> dict:
    return {c.name: getattr(partner, c.name) for c in partner.__table__.columns}


def _pipeline_totals_for_deals(db: Session, deal_ids):
    """Sum pipeline-included quote totals per deal — same semantics as the
    helper in ``deal_registrations_router._pipeline_totals_for_deals``. Kept
    inline here to avoid a cross-router import.

    Returns ``{deal_id_str: float}``. Deals with no qualifying quotes are
    absent from the dict — distinguishes "no included quotes" from "zero".
    """
    if not deal_ids:
        return {}
    rows = (
        db.query(Quote.deal_id, func.sum(QuoteVersion.grand_total_after_discount))
        .join(
            QuoteVersion,
            (QuoteVersion.quote_id == Quote.id)
            & (QuoteVersion.version_number == Quote.active_version)
            & (QuoteVersion.is_deleted.is_(False)),
        )
        .filter(Quote.deal_id.in_(list(deal_ids)))
        .filter(Quote.include_in_pipeline.is_(True))
        .filter(~Quote.status.in_(["expired", "cancelled"]))
        .group_by(Quote.deal_id)
        .all()
    )
    return {str(deal_id): float(total) for deal_id, total in rows if total is not None}


def _serialize_checklist(checklist: PartnerActivationChecklist) -> dict:
    return {c.name: getattr(checklist, c.name) for c in checklist.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("")
def list_partners(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_organization:read_all")),
):
    query = db.query(PartnerOrganization)
    total = query.count()
    items = query.order_by(PartnerOrganization.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize(p) for p in items],
    }


@router.get("/{partner_id}")
def get_partner(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner.id):
            raise HTTPException(status_code=403, detail="Access denied")
    return _serialize(partner)


@router.post("", status_code=201)
def create_partner(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_organization:create")),
):
    if "legal_name" not in payload or not payload["legal_name"]:
        raise HTTPException(status_code=422, detail="legal_name is required")
    if "program_type" not in payload:
        raise HTTPException(status_code=422, detail="program_type is required")
    if "partner_category" not in payload:
        raise HTTPException(status_code=422, detail="partner_category is required")
    try:
        partner = PartnerOrganization(**payload)
    except TypeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")
    db.add(partner)
    db.flush()

    # FPRM-172: every partner must have a 1:1 PartnerProfile row so it can be
    # GET/PATCHed via /partner-profiles and can reach activation_complete=True.
    # Mirrors provisioning.provision_partner_from_application, which was the
    # only other code path that created this row.
    db.add(PartnerProfile(id=uuid.uuid4(), partner_org_id=partner.id))

    db.commit()
    db.refresh(partner)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_organization.create",
        object_type="partner_organization",
        object_id=partner.id,
        after=jsonable_encoder(_serialize(partner)),
        ip_address=_client_ip(request),
    )
    return _serialize(partner)


@router.patch("/{partner_id}")
def update_partner(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    role = UserRole(current_user.role)
    if role == UserRole.partner_admin:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner.id):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in {UserRole.channel_ops_admin, UserRole.system_admin, UserRole.channel_manager}:
        raise HTTPException(status_code=403, detail="Insufficient permissions to update partner")
    else:
        # AD-42 (FPRM-444): channel_manager may edit only partners assigned to
        # them; enforce_cm_scope is a no-op for channel_ops_admin + system_admin.
        enforce_cm_scope(db, current_user, partner.id, request)

    before = jsonable_encoder(_serialize(partner))
    immutable = {"id", "created_at"}
    contract_field_touched = "contract_start_date" in payload
    for key, value in payload.items():
        if key in immutable:
            continue
        if hasattr(partner, key):
            setattr(partner, key, value)
    partner.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(partner)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_organization.update",
        object_type="partner_organization",
        object_id=partner.id,
        before=before,
        after=jsonable_encoder(_serialize(partner)),
        ip_address=_client_ip(request),
    )

    # If contract_start_date changed, terms_signed may need to flip.
    if contract_field_touched:
        try:
            from activation import recalculate_activation
            recalculate_activation(db, partner.id)
        except Exception:
            pass

    return _serialize(partner)


# ---- Activation checklist (Sprint 7 / FPRM-107) ----


def _enforce_activation_read(current_user: User, partner_id: uuid.UUID) -> None:
    role = UserRole(current_user.role)
    if role in INTERNAL_ROLES:
        return
    if role in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")
        return
    raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{partner_id}/activation")
def get_activation(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    _enforce_activation_read(current_user, partner_id)
    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_id)
        .first()
    )
    if not checklist:
        # Initialise on first access for orgs provisioned before Sprint 7.
        from activation import recalculate_activation
        checklist = recalculate_activation(db, partner_id)
    return _serialize_checklist(checklist)


@router.get("/{partner_id}/activation/criteria")
def get_activation_criteria(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FPRM-270 / Sprint 17 — resolved required criteria + per-item met state.

    Returns the criterion set the recalc engine evaluates for this partner
    so the portal can render a live checklist. ``config_source`` distinguishes
    ``dynamic`` (from ``activation_checklist_config``) from ``fallback``
    (the hardcoded four-flag default).
    """
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    _enforce_activation_read(current_user, partner_id)

    from activation import (
        CRITERION_KEY_MAP,
        HARDCODED_REQUIRED_KEYS,
        recalculate_activation,
        resolve_required_criteria,
    )

    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_id)
        .first()
    )
    if checklist is None:
        checklist = recalculate_activation(db, partner_id)

    config_rows, source = resolve_required_criteria(db, partner)

    if source == "dynamic":
        criteria_to_evaluate = [
            {
                "criterion_key": row.criterion_key,
                "description": row.description or row.criterion_key.replace("_", " ").title(),
            }
            for row in config_rows
        ]
    else:
        criteria_to_evaluate = [
            {"criterion_key": key, "description": key.replace("_", " ").title()}
            for key in HARDCODED_REQUIRED_KEYS
        ]

    required_criteria = []
    for item in criteria_to_evaluate:
        key = item["criterion_key"]
        field_name = CRITERION_KEY_MAP.get(key)
        if field_name and hasattr(checklist, field_name):
            is_met = bool(getattr(checklist, field_name))
        else:
            # Unknown criterion: mirror recalc behaviour (auto-satisfied).
            is_met = True
        required_criteria.append({
            "criterion_key": key,
            "description": item["description"],
            "is_met": is_met,
        })

    activation_complete = all(c["is_met"] for c in required_criteria) if required_criteria else False

    return {
        "required_criteria": required_criteria,
        "activation_complete": activation_complete,
        "config_source": source,
    }


REVIEW_ROLES = {UserRole.channel_manager, UserRole.channel_ops_admin, UserRole.system_admin}


def _set_training(
    partner_id: uuid.UUID,
    request: Request,
    db: Session,
    current_user: User,
    *,
    value: bool,
    action: str,
):
    """Shared body for training-complete / training-reset endpoints (FPRM-145)."""
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")
    enforce_cm_scope(db, current_user, partner_id, request)  # AD-41

    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_id)
        .first()
    )
    from activation import recalculate_activation
    if not checklist:
        checklist = recalculate_activation(db, partner_id)
        # Re-query to get the persisted instance
        checklist = (
            db.query(PartnerActivationChecklist)
            .filter(PartnerActivationChecklist.partner_org_id == partner_id)
            .first()
        )

    before = jsonable_encoder(_serialize_checklist(checklist))
    checklist.baseline_training_complete = value
    db.commit()
    # Run recalc so activation_complete + activated_at update accordingly
    checklist = recalculate_activation(db, partner_id)

    log_audit_event(
        db=db,
        actor=current_user,
        action=action,
        object_type="partner_activation_checklist",
        object_id=checklist.id,
        before=before,
        after=jsonable_encoder(_serialize_checklist(checklist)),
        ip_address=_client_ip(request),
    )
    return _serialize_checklist(checklist)


@router.post("/{partner_id}/activation/training-complete")
def post_training_complete(
    partner_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark baseline training complete for a partner (FPRM-145).

    Allowed roles: ``system_admin``, ``channel_ops_admin``, ``channel_manager``.
    Sets the checklist flag and runs ``recalculate_activation`` so the gate
    can flip to ``activation_complete=True`` when the other three gates pass.
    """
    return _set_training(partner_id, request, db, current_user,
                         value=True, action="partner_activation.training_complete")


@router.post("/{partner_id}/activation/training-reset")
def post_training_reset(
    partner_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reverse a previously-set baseline training completion (FPRM-145).

    Resets the flag to False and recalculates the checklist. ``activated_at``
    is intentionally not cleared - the partner *was* activated at that moment,
    later regression is a separate state we want preserved for audit.
    """
    return _set_training(partner_id, request, db, current_user,
                         value=False, action="partner_activation.training_reset")


@router.get("/{partner_id}/commission-rates")
def get_commission_rates(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return commission_structures rows for a partner's category (FPRM-158).

    Access:
        - ``partner_admin`` (own org only - 403 on other orgs)
        - ``channel_manager`` / ``system_admin`` / any other internal role

    The rates are static per category; partner_admin should see exactly what
    applies to their own contract. Internal users can inspect any partner.
    """
    partner = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == partner_id)
        .first()
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    role = UserRole(current_user.role)
    if role in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner.id):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    code = (
        partner.partner_category.value
        if hasattr(partner.partner_category, "value")
        else str(partner.partner_category)
    )
    # Migration 031 introduced is_active for soft-delete. Hide deactivated
    # rates from partner-facing form dropdowns so admins can retire a rate
    # without it lingering as a selectable option.
    rows = (
        db.query(CommissionStructure)
        .filter(
            CommissionStructure.partner_category_code == code,
            CommissionStructure.is_active.is_(True),
        )
        .all()
    )
    items = []
    for r in rows:
        year_val = r.year.value if hasattr(r.year, "value") else str(r.year)
        items.append({
            "commission_type": r.commission_type,
            "year": year_val,
            "percentage": float(r.commission_pct) if r.commission_pct is not None else None,
            "subpartner_uplift_pct": float(r.subpartner_uplift_pct) if r.subpartner_uplift_pct is not None else None,
            "applies_to_upsell": bool(r.applies_to_upsell),
            "notes": r.notes,
        })
    return {"partner_category_code": code, "items": items}


@router.get("/{partner_id}/dashboard/summary")
def get_partner_dashboard_summary(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partner home dashboard roll-up.

    Accessible to ``partner_admin`` and ``partner_user`` of the same org
    (own-org view) and to internal admins (``system_admin``,
    ``channel_ops_admin``, ``channel_manager``) for any partner. Returns deals
    counts by status, activation progress, and document review counts for the
    requested partner organisation.

    FPRM-461 (Sprint 26 PR B) — widened from partner_admin-only to also allow
    partner_user for their OWN org (same own-org tenant scoping), mirroring the
    FPRM-458 pipeline widening. Internal-role access is unchanged; cross-org
    partner access still 403s so the tenant-isolation sweep stays green.
    """
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    role = UserRole(current_user.role)
    internal_view_roles = {
        UserRole.system_admin,
        UserRole.channel_ops_admin,
        UserRole.channel_manager,
    }
    if role in (UserRole.partner_admin, UserRole.partner_user):
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied: not your organisation")
    elif role not in internal_view_roles:
        raise HTTPException(
            status_code=403,
            detail="partner_admin, partner_user, or internal admin role required",
        )

    def _deal_count(status_value: str) -> int:
        return (
            db.query(func.count(DealRegistration.id))
            .filter(DealRegistration.partner_org_id == partner_id)
            .filter(DealRegistration.status == status_value)
            .scalar()
            or 0
        )

    deals = {
        "draft": _deal_count("draft"),
        "submitted": _deal_count("submitted"),
        "under_review": _deal_count("under_review"),
        "approved": _deal_count("approved"),
        "info_required": _deal_count("info_required"),
    }

    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_id)
        .first()
    )
    activation_items = ("profile_complete", "documents_uploaded", "terms_signed", "baseline_training_complete")
    if checklist:
        items_complete = sum(1 for field in activation_items if getattr(checklist, field))
        activation = {
            "complete": bool(checklist.activation_complete),
            "items_complete": items_complete,
            "items_total": len(activation_items),
        }
    else:
        activation = {"complete": False, "items_complete": 0, "items_total": len(activation_items)}

    def _doc_count(status_value: DocumentStatus) -> int:
        return (
            db.query(func.count(PartnerDocument.id))
            .filter(PartnerDocument.partner_org_id == partner_id)
            .filter(PartnerDocument.status == status_value)
            .scalar()
            or 0
        )

    documents = {
        "pending_review": _doc_count(DocumentStatus.pending_review),
        "approved": _doc_count(DocumentStatus.approved),
        "rejected": _doc_count(DocumentStatus.rejected),
    }

    return {"deals": deals, "activation": activation, "documents": documents}


PIPELINE_STATUSES = ("draft", "submitted", "under_review", "approved", "rejected", "info_required")


@router.get("/{partner_id}/pipeline")
def get_partner_pipeline(
    partner_id: uuid.UUID,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sprint 14 / FPRM-229 — partner-side pipeline grouped by status.

    FPRM-458 (Sprint 25 hotfix) — widened from partner_admin-only to also allow
    partner_user for their OWN org (same own-org tenant scoping as the deal list);
    amends FPRM-229. Internal roles stay 403 by design — they use
    /internal/reports/pipeline. Own-org scoping is unchanged, so cross-org access
    still 403s and the tenant-isolation sweep stays green.
    """
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    role = UserRole(current_user.role)
    if role not in (UserRole.partner_admin, UserRole.partner_user):
        raise HTTPException(status_code=403, detail="partner_admin or partner_user role required")
    if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
        raise HTTPException(status_code=403, detail="Access denied")

    q = db.query(DealRegistration).filter(DealRegistration.partner_org_id == partner_id)
    if status:
        q = q.filter(DealRegistration.status == status)
    if from_date:
        try:
            from datetime import date as _date
            from_d = _date.fromisoformat(from_date)
            q = q.filter(DealRegistration.submitted_at >= datetime.combine(from_d, datetime.min.time()))
        except ValueError:
            raise HTTPException(status_code=422, detail="from_date must be ISO YYYY-MM-DD")
    if to_date:
        try:
            from datetime import date as _date
            to_d = _date.fromisoformat(to_date)
            q = q.filter(DealRegistration.submitted_at <= datetime.combine(to_d, datetime.max.time()))
        except ValueError:
            raise HTTPException(status_code=422, detail="to_date must be ISO YYYY-MM-DD")

    deals = q.all()
    pipeline_map = _pipeline_totals_for_deals(db, {d.id for d in deals})
    grouped: dict = {s: [] for s in PIPELINE_STATUSES}
    for deal in deals:
        bucket = grouped.get(deal.status)
        if bucket is None:
            grouped.setdefault(deal.status, [])
            bucket = grouped[deal.status]
        bucket.append({
            "id": str(deal.id),
            "deal_name": deal.deal_name,
            "customer_name": deal.customer_name,
            "estimated_deal_value": deal.estimated_deal_value,
            "pipeline_total": pipeline_map.get(str(deal.id)),
            "status": deal.status,
            "submitted_at": deal.submitted_at.isoformat() if deal.submitted_at else None,
            "estimated_close_date": deal.estimated_close_date.isoformat() if deal.estimated_close_date else None,
            "commission_rate_snapshot": deal.commission_rate_snapshot,
        })
    return grouped


@router.post("/{partner_id}/activation/recalculate")
def post_activation_recalculate(
    partner_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    role = UserRole(current_user.role)
    if role not in {UserRole.channel_manager, UserRole.channel_ops_admin, UserRole.system_admin}:
        raise HTTPException(status_code=403, detail="Internal role required to trigger recalculation")
    from activation import recalculate_activation
    checklist = recalculate_activation(db, partner_id)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_activation.recalculated",
        object_type="partner_activation_checklist",
        object_id=checklist.id,
        after=jsonable_encoder(_serialize_checklist(checklist)),
        ip_address=_client_ip(request),
    )
    return _serialize_checklist(checklist)
