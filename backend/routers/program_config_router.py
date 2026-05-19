"""Sprint 13 — program configuration endpoints (FPRM-209 + FPRM-213).

Approval workflow steps (Story 1), partner tiers + eligibility rules and
activation checklist criteria (Story 2) live at ``/internal/config/*``.

Permission tiers (AD-9):
    - GET endpoints: any internal role (read-only configuration)
    - POST / PATCH endpoints: channel_ops_admin + system_admin
    - DELETE endpoints: system_admin only

Multi-step approval enforcement and dynamic activation-criteria enforcement
are deferred to Phase 5. This module only manages the configuration rows.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from audit import log_audit_event
from auth import get_current_user
from database import get_db
from models import (
    ActivationChecklistConfig,
    ApprovalWorkflowStep,
    PartnerTierConfig,
    PartnerTierEligibilityRule,
    User,
)
from roles import INTERNAL_ROLES, UserRole


router = APIRouter(prefix="/internal/config", tags=["program-config"])


WORKFLOW_TYPES = {"partner_application", "deal_registration"}
VALID_ROLES = {r.value for r in UserRole}

ELIGIBILITY_RULE_TYPES = {
    "min_deals_approved",
    "min_revenue",
    "required_certification",
    "min_win_rate",
}

CONFIG_WRITE_ROLES = {UserRole.system_admin, UserRole.channel_ops_admin}


# ---- Role guards ----------------------------------------------------------


def require_internal(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")
    return current_user


def require_config_writer(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role not in CONFIG_WRITE_ROLES:
        raise HTTPException(
            status_code=403,
            detail="system_admin or channel_ops_admin required to modify config",
        )
    return current_user


def require_system_admin(current_user: User = Depends(get_current_user)) -> User:
    try:
        role = UserRole(current_user.role)
    except ValueError:
        raise HTTPException(status_code=403, detail="Unknown role")
    if role != UserRole.system_admin:
        raise HTTPException(status_code=403, detail="system_admin required")
    return current_user


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ---- Approval workflow steps (FPRM-209) -----------------------------------


def _serialize_step(s: ApprovalWorkflowStep) -> dict:
    return {
        "id": str(s.id),
        "workflow_type": s.workflow_type,
        "step_order": s.step_order,
        "step_name": s.step_name,
        "required_role": s.required_role,
        "is_active": bool(s.is_active),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/approval-steps")
def list_approval_steps(
    workflow_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_internal),
):
    query = db.query(ApprovalWorkflowStep).filter(ApprovalWorkflowStep.is_active.is_(True))
    if workflow_type is not None:
        if workflow_type not in WORKFLOW_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"workflow_type must be one of {sorted(WORKFLOW_TYPES)}",
            )
        query = query.filter(ApprovalWorkflowStep.workflow_type == workflow_type)
    rows = (
        query
        .order_by(ApprovalWorkflowStep.workflow_type, ApprovalWorkflowStep.step_order)
        .all()
    )
    return {"items": [_serialize_step(s) for s in rows]}


@router.post("/approval-steps", status_code=201)
def create_approval_step(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    wt = payload.get("workflow_type")
    name = payload.get("step_name")
    role = payload.get("required_role")
    order = payload.get("step_order")

    if wt not in WORKFLOW_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"workflow_type must be one of {sorted(WORKFLOW_TYPES)}",
        )
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="step_name is required")
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"required_role must be one of {sorted(VALID_ROLES)}",
        )
    if not isinstance(order, int) or order < 1:
        raise HTTPException(status_code=400, detail="step_order must be a positive integer")

    step = ApprovalWorkflowStep(
        id=uuid.uuid4(),
        workflow_type=wt,
        step_order=order,
        step_name=name,
        required_role=role,
        is_active=True,
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    log_audit_event(
        db=db,
        actor=current_user,
        action="approval_workflow_step.create",
        object_type="approval_workflow_step",
        object_id=step.id,
        after=jsonable_encoder(_serialize_step(step)),
        ip_address=_client_ip(request),
    )
    return _serialize_step(step)


@router.patch("/approval-steps/{step_id}")
def update_approval_step(
    step_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    step = db.query(ApprovalWorkflowStep).filter(ApprovalWorkflowStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Approval step not found")

    before = jsonable_encoder(_serialize_step(step))
    allowed = {"step_name", "step_order", "required_role", "is_active"}
    if not isinstance(payload, dict) or not (set(payload.keys()) & allowed):
        raise HTTPException(
            status_code=400,
            detail=f"payload must include one of {sorted(allowed)}",
        )

    if "step_name" in payload:
        name = payload["step_name"]
        if not isinstance(name, str) or not name:
            raise HTTPException(status_code=400, detail="step_name must be a non-empty string")
        step.step_name = name
    if "step_order" in payload:
        order = payload["step_order"]
        if not isinstance(order, int) or order < 1:
            raise HTTPException(status_code=400, detail="step_order must be a positive integer")
        step.step_order = order
    if "required_role" in payload:
        role = payload["required_role"]
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"required_role must be one of {sorted(VALID_ROLES)}",
            )
        step.required_role = role
    if "is_active" in payload:
        step.is_active = bool(payload["is_active"])

    db.commit()
    db.refresh(step)

    log_audit_event(
        db=db,
        actor=current_user,
        action="approval_workflow_step.update",
        object_type="approval_workflow_step",
        object_id=step.id,
        before=before,
        after=jsonable_encoder(_serialize_step(step)),
        ip_address=_client_ip(request),
    )
    return _serialize_step(step)


@router.delete("/approval-steps/{step_id}")
def delete_approval_step(
    step_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    step = db.query(ApprovalWorkflowStep).filter(ApprovalWorkflowStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Approval step not found")

    before = jsonable_encoder(_serialize_step(step))
    step.is_active = False
    db.commit()
    db.refresh(step)

    log_audit_event(
        db=db,
        actor=current_user,
        action="approval_workflow_step.delete",
        object_type="approval_workflow_step",
        object_id=step.id,
        before=before,
        after=jsonable_encoder(_serialize_step(step)),
        ip_address=_client_ip(request),
    )
    return _serialize_step(step)


# ---- Partner tier configuration (FPRM-213) --------------------------------


def _serialize_rule(r: PartnerTierEligibilityRule) -> dict:
    return {
        "id": str(r.id),
        "tier_id": str(r.tier_id),
        "rule_type": r.rule_type,
        "rule_value": r.rule_value,
        "description": r.description,
    }


def _serialize_tier(t: PartnerTierConfig) -> dict:
    return {
        "id": str(t.id),
        "tier_name": t.tier_name,
        "tier_rank": t.tier_rank,
        "description": t.description,
        "is_active": bool(t.is_active),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "eligibility_rules": [_serialize_rule(r) for r in (t.eligibility_rules or [])],
    }


@router.get("/tiers")
def list_tiers(
    db: Session = Depends(get_db),
    _: User = Depends(require_internal),
):
    rows = (
        db.query(PartnerTierConfig)
        .filter(PartnerTierConfig.is_active.is_(True))
        .order_by(PartnerTierConfig.tier_rank.asc())
        .all()
    )
    return {"items": [_serialize_tier(t) for t in rows]}


@router.post("/tiers", status_code=201)
def create_tier(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    name = payload.get("tier_name")
    rank = payload.get("tier_rank")
    description = payload.get("description")

    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="tier_name is required")
    if not isinstance(rank, int) or rank < 1:
        raise HTTPException(status_code=400, detail="tier_rank must be a positive integer")

    existing = db.query(PartnerTierConfig).filter(PartnerTierConfig.tier_name == name).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Tier '{name}' already exists")

    tier = PartnerTierConfig(
        id=uuid.uuid4(),
        tier_name=name,
        tier_rank=rank,
        description=description,
        is_active=True,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_tier.create",
        object_type="partner_tier",
        object_id=tier.id,
        after=jsonable_encoder(_serialize_tier(tier)),
        ip_address=_client_ip(request),
    )
    return _serialize_tier(tier)


@router.patch("/tiers/{tier_id}")
def update_tier(
    tier_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    tier = db.query(PartnerTierConfig).filter(PartnerTierConfig.id == tier_id).first()
    if not tier:
        raise HTTPException(status_code=404, detail="Tier not found")

    before = jsonable_encoder(_serialize_tier(tier))
    allowed = {"tier_name", "tier_rank", "description", "is_active"}
    if not isinstance(payload, dict) or not (set(payload.keys()) & allowed):
        raise HTTPException(
            status_code=400,
            detail=f"payload must include one of {sorted(allowed)}",
        )

    if "tier_name" in payload:
        name = payload["tier_name"]
        if not isinstance(name, str) or not name:
            raise HTTPException(status_code=400, detail="tier_name must be a non-empty string")
        # Uniqueness check excluding self
        clash = (
            db.query(PartnerTierConfig)
            .filter(PartnerTierConfig.tier_name == name)
            .filter(PartnerTierConfig.id != tier_id)
            .first()
        )
        if clash is not None:
            raise HTTPException(status_code=409, detail=f"Tier '{name}' already exists")
        tier.tier_name = name
    if "tier_rank" in payload:
        rank = payload["tier_rank"]
        if not isinstance(rank, int) or rank < 1:
            raise HTTPException(status_code=400, detail="tier_rank must be a positive integer")
        tier.tier_rank = rank
    if "description" in payload:
        desc = payload["description"]
        if desc is not None and not isinstance(desc, str):
            raise HTTPException(status_code=400, detail="description must be a string or null")
        tier.description = desc
    if "is_active" in payload:
        tier.is_active = bool(payload["is_active"])

    db.commit()
    db.refresh(tier)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_tier.update",
        object_type="partner_tier",
        object_id=tier.id,
        before=before,
        after=jsonable_encoder(_serialize_tier(tier)),
        ip_address=_client_ip(request),
    )
    return _serialize_tier(tier)


@router.post("/tiers/{tier_id}/eligibility-rules", status_code=201)
def add_eligibility_rule(
    tier_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    tier = db.query(PartnerTierConfig).filter(PartnerTierConfig.id == tier_id).first()
    if not tier:
        raise HTTPException(status_code=404, detail="Tier not found")

    rule_type = payload.get("rule_type")
    rule_value = payload.get("rule_value")
    description = payload.get("description")

    if rule_type not in ELIGIBILITY_RULE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"rule_type must be one of {sorted(ELIGIBILITY_RULE_TYPES)}",
        )
    if rule_value is None:
        raise HTTPException(status_code=400, detail="rule_value is required")
    rule_value = str(rule_value)

    rule = PartnerTierEligibilityRule(
        id=uuid.uuid4(),
        tier_id=tier.id,
        rule_type=rule_type,
        rule_value=rule_value,
        description=description if isinstance(description, str) else None,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_tier.eligibility_rule_added",
        object_type="partner_tier_eligibility_rule",
        object_id=rule.id,
        after=jsonable_encoder(_serialize_rule(rule)),
        ip_address=_client_ip(request),
    )
    return _serialize_rule(rule)


@router.delete("/tiers/{tier_id}/eligibility-rules/{rule_id}")
def delete_eligibility_rule(
    tier_id: uuid.UUID,
    rule_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    rule = (
        db.query(PartnerTierEligibilityRule)
        .filter(PartnerTierEligibilityRule.id == rule_id)
        .filter(PartnerTierEligibilityRule.tier_id == tier_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Eligibility rule not found")

    before = jsonable_encoder(_serialize_rule(rule))
    db.delete(rule)
    db.commit()

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_tier.eligibility_rule_deleted",
        object_type="partner_tier_eligibility_rule",
        object_id=rule_id,
        before=before,
        ip_address=_client_ip(request),
    )
    return {"deleted": str(rule_id)}


# ---- Activation checklist configuration (FPRM-213) ------------------------


def _serialize_criterion(c: ActivationChecklistConfig) -> dict:
    return {
        "id": str(c.id),
        "partner_category_code": c.partner_category_code,
        "tier_name": c.tier_name,
        "criterion_key": c.criterion_key,
        "is_required": bool(c.is_required),
        "description": c.description,
        "is_active": bool(c.is_active),
    }


@router.get("/activation-criteria")
def list_activation_criteria(
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_internal),
):
    query = db.query(ActivationChecklistConfig)
    if is_active is not None:
        query = query.filter(ActivationChecklistConfig.is_active.is_(is_active))
    rows = query.order_by(ActivationChecklistConfig.criterion_key).all()
    return {"items": [_serialize_criterion(c) for c in rows]}


@router.post("/activation-criteria", status_code=201)
def create_activation_criterion(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    key = payload.get("criterion_key")
    if not key or not isinstance(key, str):
        raise HTTPException(status_code=400, detail="criterion_key is required")

    is_required = payload.get("is_required", True)
    if not isinstance(is_required, bool):
        raise HTTPException(status_code=400, detail="is_required must be a boolean")

    category = payload.get("partner_category_code")
    tier_name = payload.get("tier_name")
    description = payload.get("description")
    for field, value in (("partner_category_code", category), ("tier_name", tier_name),
                         ("description", description)):
        if value is not None and not isinstance(value, str):
            raise HTTPException(status_code=400, detail=f"{field} must be a string or null")

    crit = ActivationChecklistConfig(
        id=uuid.uuid4(),
        partner_category_code=category,
        tier_name=tier_name,
        criterion_key=key,
        is_required=is_required,
        description=description,
        is_active=True,
    )
    db.add(crit)
    db.commit()
    db.refresh(crit)

    log_audit_event(
        db=db,
        actor=current_user,
        action="activation_criterion.create",
        object_type="activation_checklist_config",
        object_id=crit.id,
        after=jsonable_encoder(_serialize_criterion(crit)),
        ip_address=_client_ip(request),
    )
    return _serialize_criterion(crit)


@router.patch("/activation-criteria/{criterion_id}")
def update_activation_criterion(
    criterion_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_config_writer),
):
    crit = (
        db.query(ActivationChecklistConfig)
        .filter(ActivationChecklistConfig.id == criterion_id)
        .first()
    )
    if not crit:
        raise HTTPException(status_code=404, detail="Criterion not found")

    before = jsonable_encoder(_serialize_criterion(crit))
    allowed = {"is_required", "is_active", "description", "partner_category_code", "tier_name"}
    if not isinstance(payload, dict) or not (set(payload.keys()) & allowed):
        raise HTTPException(
            status_code=400,
            detail=f"payload must include one of {sorted(allowed)}",
        )

    if "is_required" in payload:
        if not isinstance(payload["is_required"], bool):
            raise HTTPException(status_code=400, detail="is_required must be a boolean")
        crit.is_required = payload["is_required"]
    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            raise HTTPException(status_code=400, detail="is_active must be a boolean")
        crit.is_active = payload["is_active"]
    for field in ("description", "partner_category_code", "tier_name"):
        if field in payload:
            value = payload[field]
            if value is not None and not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"{field} must be a string or null")
            setattr(crit, field, value)

    db.commit()
    db.refresh(crit)

    log_audit_event(
        db=db,
        actor=current_user,
        action="activation_criterion.update",
        object_type="activation_checklist_config",
        object_id=crit.id,
        before=before,
        after=jsonable_encoder(_serialize_criterion(crit)),
        ip_address=_client_ip(request),
    )
    return _serialize_criterion(crit)


@router.delete("/activation-criteria/{criterion_id}")
def delete_activation_criterion(
    criterion_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_system_admin),
):
    crit = (
        db.query(ActivationChecklistConfig)
        .filter(ActivationChecklistConfig.id == criterion_id)
        .first()
    )
    if not crit:
        raise HTTPException(status_code=404, detail="Criterion not found")

    before = jsonable_encoder(_serialize_criterion(crit))
    crit.is_active = False
    db.commit()
    db.refresh(crit)

    log_audit_event(
        db=db,
        actor=current_user,
        action="activation_criterion.delete",
        object_type="activation_checklist_config",
        object_id=crit.id,
        before=before,
        after=jsonable_encoder(_serialize_criterion(crit)),
        ip_address=_client_ip(request),
    )
    return _serialize_criterion(crit)
