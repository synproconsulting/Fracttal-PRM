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
from models import ApprovalWorkflowStep, User
from roles import INTERNAL_ROLES, UserRole


router = APIRouter(prefix="/internal/config", tags=["program-config"])


WORKFLOW_TYPES = {"partner_application", "deal_registration"}
VALID_ROLES = {r.value for r in UserRole}

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
