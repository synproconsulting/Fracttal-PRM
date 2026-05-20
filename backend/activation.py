"""Partner activation checklist recalculation.

FPRM-107 / Sprint 7 established the original four-flag gate.
FPRM-145 added baseline_training_complete.
FPRM-270 / Sprint 17 made the *required-criteria selection* dynamic — the
function now reads ``activation_checklist_config`` (migration 022) and falls
back to the hardcoded four-flag rule when no rows match the partner's
category / tier. The per-flag computations themselves are unchanged.

``recalculate_activation`` remains the single source of truth (AD-14). Its
signature is frozen — every caller still passes ``(db, partner_org_id)`` and
receives the freshly persisted ``PartnerActivationChecklist`` row.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import (
    ActivationChecklistConfig,
    DocumentStatus,
    PartnerActivationChecklist,
    PartnerDocument,
    PartnerOrganization,
    PartnerProfile,
)


# Map a configured ``criterion_key`` to the boolean field on
# ``PartnerActivationChecklist`` that backs it. Keys whose mapped field does
# not exist on the model (or whose key is absent from this map) are skipped
# gracefully during evaluation — admins can add new criterion vocabulary
# entries before their model backing is implemented without locking every
# partner out of activation.
CRITERION_KEY_MAP = {
    "profile_complete": "profile_complete",
    "documents_uploaded": "documents_uploaded",
    "baseline_training_complete": "baseline_training_complete",
    "terms_signed": "terms_signed",
    # ``contract_signed`` is the spec wording for what the checklist tracks as
    # ``terms_signed`` (contract_start_date populated) — alias both to the
    # same field so either configured key flips activation correctly.
    "contract_signed": "terms_signed",
    "training_complete": "baseline_training_complete",
}


# The four flags that have been required since FPRM-145. Used as the
# fallback set when no ``ActivationChecklistConfig`` rows match the partner
# (preserves legacy behaviour for orgs provisioned before Sprint 17).
HARDCODED_REQUIRED_KEYS = [
    "profile_complete",
    "documents_uploaded",
    "baseline_training_complete",
    "terms_signed",
]


def _enum_value(value):
    """Return ``value.value`` for enum members, else the value itself."""
    return value.value if hasattr(value, "value") else value


def resolve_required_criteria(
    db: Session,
    partner: Optional[PartnerOrganization],
) -> Tuple[Optional[List[ActivationChecklistConfig]], str]:
    """Return ``(config_rows, source)`` where ``source`` is ``"dynamic"`` or ``"fallback"``.

    ``config_rows`` is the list of ``ActivationChecklistConfig`` rows that
    apply to the partner (active + required, matching category and tier
    either exactly or via the catch-all ``NULL`` row). If the resulting set
    is empty (no rows match, or the partner is missing), ``source`` is
    ``"fallback"`` and the caller should use ``HARDCODED_REQUIRED_KEYS``.
    """
    if partner is None:
        return None, "fallback"

    cat_val = _enum_value(partner.partner_category)
    tier_val = _enum_value(partner.tier)

    config_rows = (
        db.query(ActivationChecklistConfig)
        .filter(
            ActivationChecklistConfig.is_active == True,  # noqa: E712
            ActivationChecklistConfig.is_required == True,  # noqa: E712
            or_(
                ActivationChecklistConfig.partner_category_code == cat_val,
                ActivationChecklistConfig.partner_category_code.is_(None),
            ),
            or_(
                ActivationChecklistConfig.tier_name == tier_val,
                ActivationChecklistConfig.tier_name.is_(None),
            ),
        )
        .all()
    )

    if config_rows:
        return config_rows, "dynamic"
    return None, "fallback"


def _criterion_is_met(checklist: PartnerActivationChecklist, criterion_key: str) -> bool:
    """Resolve whether a single criterion is satisfied for the given checklist.

    Unknown criterion keys (no mapping) and mapped fields that don't exist
    on the checklist are treated as auto-satisfied so an admin adding a
    not-yet-supported criterion key doesn't permanently block activation.
    """
    field_name = CRITERION_KEY_MAP.get(criterion_key)
    if field_name is None:
        return True
    if not hasattr(checklist, field_name):
        return True
    return bool(getattr(checklist, field_name))


def recalculate_activation(db: Session, partner_org_id) -> PartnerActivationChecklist:
    """Recompute every checklist field for a partner org and persist.

    Returns the freshly-saved ``PartnerActivationChecklist`` row. Creates the
    row if it does not yet exist. Signature is frozen — all callers pass
    ``(db, partner_org_id)`` and rely on the returned checklist.
    """
    checklist = (
        db.query(PartnerActivationChecklist)
        .filter(PartnerActivationChecklist.partner_org_id == partner_org_id)
        .first()
    )
    if checklist is None:
        checklist = PartnerActivationChecklist(partner_org_id=partner_org_id)
        db.add(checklist)

    org = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == partner_org_id)
        .first()
    )
    profile = (
        db.query(PartnerProfile)
        .filter(PartnerProfile.partner_org_id == partner_org_id)
        .first()
    )

    # profile_complete — profile_completeness_pct >= 80
    pct = (profile.profile_completeness_pct or 0) if profile else 0
    checklist.profile_complete = pct >= 80

    # documents_uploaded — at least one approved document (FPRM-156).
    if org is not None:
        approved_count = (
            db.query(PartnerDocument)
            .filter(
                PartnerDocument.partner_org_id == partner_org_id,
                PartnerDocument.status == DocumentStatus.approved,
            )
            .count()
        )
        checklist.documents_uploaded = approved_count >= 1
    else:
        checklist.documents_uploaded = False

    # terms_signed — contract_start_date is set on the partner org
    checklist.terms_signed = bool(org and org.contract_start_date)

    # baseline_training_complete — preserve admin-set value (FPRM-145).
    if checklist.baseline_training_complete is None:
        checklist.baseline_training_complete = False

    # activation_complete — gated dynamically by ActivationChecklistConfig
    # (FPRM-270 / Sprint 17). Falls back to HARDCODED_REQUIRED_KEYS when
    # no config rows match the partner — preserving the legacy four-flag
    # rule for existing prod data.
    was_complete = checklist.activation_complete
    config_rows, source = resolve_required_criteria(db, org)
    if source == "dynamic":
        required_keys = [row.criterion_key for row in config_rows]
    else:
        required_keys = HARDCODED_REQUIRED_KEYS

    all_met = all(_criterion_is_met(checklist, k) for k in required_keys) if required_keys else False

    checklist.activation_complete = bool(all_met)
    if checklist.activation_complete and not was_complete:
        checklist.activated_at = datetime.utcnow()

    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(checklist)
    return checklist
