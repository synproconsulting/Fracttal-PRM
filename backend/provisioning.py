"""Partner provisioning utility.

Sprint 6 / FPRM-92. Called from ``POST /applications/{id}/approve`` once the
application is in status=approved. Creates the full partner record:

    1. PartnerOrganization (status=active)
    2. PartnerProfile linked to the new org
    3. PartnerUserInvite for the applicant_email with invited_role=partner_admin,
       7-day expiry, fresh ``token`` value (hex UUID)

Returns ``{partner_org_id, invite_token}``. The caller is responsible for
writing the ``partner_application.approved`` audit entry (which it already does
in ``applications_router.approve_application``).

This module is imported lazily by the router so a missing provisioning.py
during Sprint 6 Story 1 only (before Story 3 lands) degrades gracefully —
the approve endpoint still flips status but no partner is provisioned.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import (
    InvitedRole,
    PartnerApplication,
    PartnerCategory,
    PartnerOrganization,
    PartnerProfile,
    PartnerStatus,
    PartnerUserInvite,
    ProgramType,
)


def _coerce_category(requested) -> PartnerCategory:
    """Pick the first requested category that maps to a valid PartnerCategory.

    Falls back to PartnerCategory.reseller if nothing usable was supplied.
    """
    if isinstance(requested, list):
        for candidate in requested:
            if not isinstance(candidate, str):
                continue
            value = candidate.strip().lower()
            try:
                return PartnerCategory(value)
            except ValueError:
                continue
    return PartnerCategory.reseller


def provision_partner_from_application(
    db: Session,
    application_id,
    reviewer_id: Optional[uuid.UUID],
) -> dict:
    """Provision a new partner from an approved application.

    Idempotent on the application: if ``partner_org_id`` is already set the
    existing partner is returned without recreating any rows.
    """
    application = db.query(PartnerApplication).filter(PartnerApplication.id == application_id).first()
    if application is None:
        raise ValueError(f"Application {application_id} not found")

    if application.partner_org_id:
        existing_invite = (
            db.query(PartnerUserInvite)
            .filter(PartnerUserInvite.partner_org_id == application.partner_org_id)
            .order_by(PartnerUserInvite.created_at.desc())
            .first()
        )
        return {
            "partner_org_id": application.partner_org_id,
            "invite_token": existing_invite.token if existing_invite else None,
            "already_provisioned": True,
        }

    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=application.legal_name or (application.applicant_name or "Pending Partner"),
        dba_name=application.dba_name,
        website=application.website,
        hq_address=application.hq_address,
        phone=application.phone,
        email=application.applicant_email,
        program_type=ProgramType.distributor,
        partner_category=_coerce_category(application.requested_categories),
        territory=application.territory,
        industries=application.industries,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.flush()  # so org.id is available without commit

    profile = PartnerProfile(
        id=uuid.uuid4(),
        partner_org_id=org.id,
        year_established=application.year_established,
        employee_count=application.employee_count,
        annual_revenue=application.annual_revenue,
        shareholders=application.shareholders,
        cmms_experience=application.cmms_experience,
        cmms_experience_description=application.cmms_experience_description,
        other_software_products=application.other_software_products,
        sales_marketing_strategy=application.sales_marketing_strategy,
        technical_support_team=application.technical_support_team,
        technical_support_description=application.technical_support_description,
        implementation_services=application.implementation_services,
        implementation_description=application.implementation_description,
        partnership_goals=application.partnership_goals,
        market_growth_plan=application.market_growth_plan,
        additional_info=application.additional_info,
    )
    db.add(profile)

    invite_token = uuid.uuid4().hex
    invite_invited_by = reviewer_id
    if invite_invited_by is None:
        # FK on partner_user_invites.invited_by_user_id is NOT NULL; fall back to a
        # placeholder UUID — provisioning callers always have a reviewer id, this is
        # belt-and-braces for paths that bypass the approve endpoint.
        invite_invited_by = uuid.uuid4()
    invite = PartnerUserInvite(
        id=uuid.uuid4(),
        partner_org_id=org.id,
        email=application.applicant_email,
        invited_role=InvitedRole.partner_admin,
        token=invite_token,
        invited_by_user_id=invite_invited_by,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)

    application.partner_org_id = org.id
    application.reviewer_id = reviewer_id
    application.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(org)

    return {
        "partner_org_id": org.id,
        "invite_token": invite_token,
        "already_provisioned": False,
    }
