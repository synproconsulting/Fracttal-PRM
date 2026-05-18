"""Deal conflict checker (Sprint 10 / FPRM-157).

Detects when two partners attempt to register a deal against the same customer
(matched on ``customer_domain``). The checker runs after a deal transitions
into ``submitted``; the result is stored on the deal row so reviewers can
surface it in the queue and detail page.

The module is intentionally a standalone utility — no FastAPI dependencies, no
audit-log calls, no Session creation. The router supplies a Session and a
deal id, and the function returns a ``ConflictResult`` dataclass that the
router persists. This matches the AD-14 pattern (``activation.py`` is the
single source of truth for activation state) and keeps the conflict logic
testable in isolation.
"""
from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from models import DealRegistration


ACTIVE_STATUSES = ("submitted", "under_review", "approved")


@dataclass
class ConflictResult:
    """Outcome of ``check_deal_conflict``.

    Attributes:
        conflict_status: ``"clear"`` | ``"conflict_detected"`` | ``"not_checked"``
        conflicting_deal_ids: ids of other partners' active deals on the same domain
        notes: human-readable summary persisted to ``DealRegistration.conflict_notes``
    """

    conflict_status: str
    conflicting_deal_ids: List[UUID] = field(default_factory=list)
    notes: str = ""


def check_deal_conflict(db: Session, deal_id: UUID) -> ConflictResult:
    """Resolve conflict state for ``deal_id`` against currently active deals.

    Returns ``not_checked`` when the deal has no ``customer_domain`` (the
    checker has nothing reliable to match on); ``conflict_detected`` when any
    other partner has an active deal on the same domain; ``clear`` otherwise.
    """
    deal = (
        db.query(DealRegistration)
        .filter(DealRegistration.id == deal_id)
        .first()
    )
    if deal is None:
        return ConflictResult(conflict_status="not_checked", notes="Deal not found")
    if not (deal.customer_domain or "").strip():
        return ConflictResult(
            conflict_status="not_checked",
            notes="No customer domain provided",
        )

    conflicts = (
        db.query(DealRegistration)
        .filter(
            DealRegistration.customer_domain == deal.customer_domain,
            DealRegistration.partner_org_id != deal.partner_org_id,
            DealRegistration.status.in_(ACTIVE_STATUSES),
            DealRegistration.id != deal_id,
        )
        .all()
    )
    if conflicts:
        return ConflictResult(
            conflict_status="conflict_detected",
            conflicting_deal_ids=[c.id for c in conflicts],
            notes=(
                f"Conflict detected with {len(conflicts)} active deal(s) "
                f"for domain {deal.customer_domain}"
            ),
        )
    return ConflictResult(conflict_status="clear", notes="No conflicts found")
