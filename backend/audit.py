"""
Audit trail utility for Fracttal PRM.

All significant state changes must be logged via log_audit_event.
This includes: partner profile updates, deal approvals/rejections,
quote approvals, user role changes, tier changes.

Usage:
    from audit import log_audit_event

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_profile.update",
        object_type="partner_organization",
        object_id=partner.id,
        before=before_state_dict,
        after=after_state_dict,
        ip_address=request.client.host,
    )
"""
import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

from models import AuditLog


def log_audit_event(
    db: Session,
    actor,
    action: str,
    object_type: str,
    object_id: Optional[Any] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    ip_address: Optional[str] = None,
    notes: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry for a significant state change.

    Args:
        db:          active database session
        actor:       the User performing the action, or ``None`` for unauthenticated
                     events (e.g. public partner application submission)
        action:      dot-notation action string e.g. ``deal_registration.approve``
        object_type: the type of object being acted on e.g. ``deal_registration``
        object_id:   UUID of the object (optional for list/bulk actions)
        before:      state dict before the change (optional)
        after:       state dict after the change (optional)
        ip_address:  requesting IP address (optional)
        notes:       free-text notes (optional)

    Returns:
        The created AuditLog instance (already committed to the DB).
    """
    entry = AuditLog(
        id=uuid.uuid4(),
        timestamp=datetime.utcnow(),
        actor_id=actor.id if actor is not None else None,
        actor_role=actor.role if actor is not None else "anonymous",
        action=action,
        object_type=object_type,
        object_id=object_id,
        before_state=before,
        after_state=after,
        ip_address=ip_address,
        notes=notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
