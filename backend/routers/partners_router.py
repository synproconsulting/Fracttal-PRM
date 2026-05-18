"""Partner organization CRUD endpoints + activation checklist endpoints.

Permissions:
    GET    /partners                                  - partner_organization:read_all (internal)
    GET    /partners/{id}                             - any authenticated (partner-side limited to own org)
    POST   /partners                                  - partner_organization:create (channel_ops_admin, system_admin)
    PATCH  /partners/{id}                             - channel_ops_admin/system_admin (any) or partner_admin (own org)
    GET    /partners/{id}/activation                  - partner_admin (own org) or any internal role
    POST   /partners/{id}/activation/recalculate      - channel_manager / channel_ops_admin / system_admin

Sprint 7 / FPRM-107 — activation endpoints. PATCH /partners/{id} now also
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
from models import PartnerActivationChecklist, PartnerOrganization, User
from permissions import require_permission
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partners"])


def _serialize(partner: PartnerOrganization) -> dict:
    return {c.name: getattr(partner, c.name) for c in partner.__table__.columns}


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
    elif role not in {UserRole.channel_ops_admin, UserRole.system_admin}:
        raise HTTPException(status_code=403, detail="Insufficient permissions to update partner")

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
    is intentionally not cleared — the partner *was* activated at that moment,
    later regression is a separate state we want preserved for audit.
    """
    return _set_training(partner_id, request, db, current_user,
                         value=False, action="partner_activation.training_reset")


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
