"""Shared multi-step approval helpers (FPRM-274 / Sprint 17).

Both ``applications_router`` and ``deal_registrations_router`` need to:
  - resolve the configured ``approval_workflow_steps`` for the workflow
  - figure out which step is "current" (next uncompleted) for a given object
  - count completed steps for an object
  - render a stable ``approval_progress`` summary for GET responses

Keeping these as router-level inline helpers would either duplicate the
code or force a cross-router import (which risks circulars). This module
imports only ``models`` and is safe to import from anywhere in the backend.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from models import ApprovalStepRecord, ApprovalWorkflowStep


WORKFLOW_PARTNER_APPLICATION = "partner_application"
WORKFLOW_DEAL_REGISTRATION = "deal_registration"


def get_approval_step_context(
    db: Session,
    workflow_type: str,
    object_id,
) -> Tuple[List[ApprovalWorkflowStep], Optional[ApprovalWorkflowStep], int]:
    """Return ``(steps, current_step, completed_count)`` for a workflow object.

    - ``steps`` is the ordered list of active ApprovalWorkflowStep rows for
      the workflow type. Empty list = no steps configured (legacy fallback).
    - ``current_step`` is the lowest step_order whose order has not yet been
      approved for ``object_id``. ``None`` once every step is approved or
      when there are no steps at all.
    - ``completed_count`` is the number of distinct step_orders that have an
      ``action="approved"`` record for this object.
    """
    steps = (
        db.query(ApprovalWorkflowStep)
        .filter(
            ApprovalWorkflowStep.workflow_type == workflow_type,
            ApprovalWorkflowStep.is_active == True,  # noqa: E712
        )
        .order_by(ApprovalWorkflowStep.step_order)
        .all()
    )
    if not steps:
        return [], None, 0

    approved_records = (
        db.query(ApprovalStepRecord)
        .filter(
            ApprovalStepRecord.workflow_type == workflow_type,
            ApprovalStepRecord.object_id == object_id,
            ApprovalStepRecord.action == "approved",
        )
        .all()
    )
    completed_orders = {r.step_order for r in approved_records}
    completed_count = len(completed_orders)

    current_step = None
    for step in steps:
        if step.step_order not in completed_orders:
            current_step = step
            break

    return steps, current_step, completed_count


def build_approval_progress(
    steps: List[ApprovalWorkflowStep],
    completed_count: int,
) -> Optional[dict]:
    """Build the ``approval_progress`` block for GET responses.

    Returns ``None`` when no steps are configured (the legacy/fallback path)
    so client code can branch on its presence to decide whether to render
    a multi-step progress indicator.
    """
    if not steps:
        return None
    total = len(steps)
    if completed_count >= total:
        return {
            "total_steps": total,
            "completed_steps": completed_count,
            "current_step_order": None,
            "current_step_name": None,
            "current_required_role": None,
        }
    next_step = steps[completed_count]
    return {
        "total_steps": total,
        "completed_steps": completed_count,
        "current_step_order": next_step.step_order,
        "current_step_name": next_step.step_name,
        "current_required_role": next_step.required_role,
    }


def record_step_action(
    db: Session,
    *,
    workflow_type: str,
    object_id,
    step: ApprovalWorkflowStep,
    actor_id,
    action: str,
    notes: Optional[str] = None,
) -> ApprovalStepRecord:
    """Append an ApprovalStepRecord. Caller is responsible for ``db.commit()``."""
    from datetime import datetime
    record = ApprovalStepRecord(
        workflow_type=workflow_type,
        object_id=object_id,
        step_order=step.step_order,
        step_name=step.step_name,
        required_role=step.required_role,
        actor_id=actor_id,
        action=action,
        notes=notes,
        actioned_at=datetime.utcnow(),
    )
    db.add(record)
    return record
