"""Partner activation checklist recalculation (FPRM-107 / Sprint 7 / AD-14).

A partner is "activated" once they have:
  - A reasonably complete profile (profile_completeness_pct >= 80)
  - At least one approved compliance document (FPRM-156 simplified the rule —
    the document_types vocabulary became admin-configurable in FPRM-144, so the
    hardcoded ``fiscal_id`` + ``id_legal_representative`` requirement no longer
    fit. Reviewers approve whichever documents the partner is required to
    submit for their territory.)
  - A signed partnership agreement (proxied by partner_organizations.contract_start_date)
  - Baseline training completed (FPRM-145 — set via the activation/training-complete endpoint)

``recalculate_activation`` is the single source of truth for these computations. It
runs after every profile update, document approval, and contract-date change, plus
on demand via ``POST /partners/{id}/activation/recalculate``. It is idempotent and
auto-creates the checklist row if one is missing (for partner orgs provisioned
before Sprint 7 / FPRM-107).
"""
from datetime import datetime

from sqlalchemy.orm import Session

from models import (
    DocumentStatus,
    PartnerActivationChecklist,
    PartnerDocument,
    PartnerOrganization,
    PartnerProfile,
)


def recalculate_activation(db: Session, partner_org_id) -> PartnerActivationChecklist:
    """Recompute every checklist field for a partner org and persist.

    Returns the freshly-saved PartnerActivationChecklist row. Creates the row
    if it does not yet exist (useful for partner orgs provisioned before this
    feature shipped).
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
    # The earlier "both fiscal_id and id_legal_representative must be approved"
    # rule broke once FPRM-144 made document_types admin-configurable: partners
    # outside the original two required types could never flip the flag.
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

    # baseline_training_complete — FPRM-145: preserve whatever the
    # POST /partners/{id}/activation/training-{complete,reset} endpoints set.
    # Recalc never flips it; it is admin/manager-driven.
    if checklist.baseline_training_complete is None:
        checklist.baseline_training_complete = False

    # activation_complete — all four required gates True (FPRM-145 added
    # baseline_training_complete to the gate; previously it was hardcoded
    # False and excluded, leaving partners able to activate without training).
    was_complete = checklist.activation_complete
    checklist.activation_complete = bool(
        checklist.profile_complete
        and checklist.documents_uploaded
        and checklist.terms_signed
        and checklist.baseline_training_complete
    )
    if checklist.activation_complete and not was_complete:
        checklist.activated_at = datetime.utcnow()

    checklist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(checklist)
    return checklist
