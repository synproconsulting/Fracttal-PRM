"""Partner profile endpoints (FPRM-106 / Sprint 7).

The PartnerProfile table is a 1:1 child of PartnerOrganization, so we key these
endpoints by ``partner_org_id`` rather than the profile's own UUID — both for
caller ergonomics (the frontend always has the org id from the JWT) and to keep
the partner-side route shape consistent with ``/partners/{id}``.

Endpoints:
    GET    /partner-profiles/{partner_org_id}    any authenticated user (partner-side limited to own org)
    PATCH  /partner-profiles/{partner_org_id}    partner_admin (own org) or channel_ops_admin / system_admin

Profile completeness is recomputed on every PATCH and stored on the profile row.
The activation recalc call uses a try/except stub until backend/activation.py
lands in Story 3 (FPRM-107); after that the import resolves and partner-side
activation status updates as soon as the profile crosses the 80% threshold.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import PartnerProfile, User
from permissions import enforce_cm_scope
from roles import PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partner-profiles", tags=["partner-profiles"])


PROFILE_FIELDS = [
    "year_established",
    "employee_count",
    "annual_revenue",
    "shareholders",
    "other_software_products",
    "cmms_experience",
    "sales_marketing_strategy",
    "technical_support_team",
    "implementation_services",
    "partnership_goals",
    "market_growth_plan",
]


WRITABLE_FIELDS = set(PROFILE_FIELDS) | {
    "cmms_experience_description",
    "technical_support_description",
    "implementation_description",
    "additional_info",
}


def calculate_profile_completeness(profile: PartnerProfile) -> int:
    """Percentage of PROFILE_FIELDS that are non-null. Returns int 0..100."""
    filled = sum(1 for f in PROFILE_FIELDS if getattr(profile, f, None) is not None)
    return round(filled / len(PROFILE_FIELDS) * 100)


def _serialize(profile: PartnerProfile) -> dict:
    return {c.name: getattr(profile, c.name) for c in profile.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _enforce_tenant(current_user: User, partner_org_id: uuid.UUID, *, write: bool) -> None:
    role = UserRole(current_user.role)
    if write:
        if role == UserRole.partner_admin:
            if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_org_id):
                raise HTTPException(status_code=403, detail="Access denied")
        elif role not in {UserRole.channel_ops_admin, UserRole.system_admin, UserRole.channel_manager}:
            raise HTTPException(status_code=403, detail="Insufficient permissions to update partner profile")
        return

    if role in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_org_id):
            raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{partner_org_id}")
def get_partner_profile(
    partner_org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = (
        db.query(PartnerProfile).filter(PartnerProfile.partner_org_id == partner_org_id).first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Partner profile not found")
    _enforce_tenant(current_user, partner_org_id, write=False)
    return _serialize(profile)


@router.patch("/{partner_org_id}")
def update_partner_profile(
    partner_org_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = (
        db.query(PartnerProfile).filter(PartnerProfile.partner_org_id == partner_org_id).first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Partner profile not found")
    _enforce_tenant(current_user, partner_org_id, write=True)
    # AD-42 (FPRM-444): channel_manager may edit only assigned partners' profiles;
    # no-op for partner_admin (own-org checked above) + admins (always unscoped).
    enforce_cm_scope(db, current_user, partner_org_id, request)

    before = jsonable_encoder(_serialize(profile))
    for key, value in payload.items():
        if key not in WRITABLE_FIELDS:
            continue
        setattr(profile, key, value)
    profile.profile_completeness_pct = calculate_profile_completeness(profile)
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_profile.update",
        object_type="partner_profile",
        object_id=profile.id,
        before=before,
        after=jsonable_encoder(_serialize(profile)),
        ip_address=_client_ip(request),
    )

    # Activation recalc is best-effort — Story 3 (FPRM-107) introduces activation.py.
    # Until then the import fails and we no-op silently. After Story 3 merges, profile
    # updates immediately propagate to PartnerActivationChecklist.profile_complete.
    try:
        from activation import recalculate_activation  # noqa: WPS433 — lazy by design
        recalculate_activation(db, partner_org_id)
    except Exception:
        pass

    return _serialize(profile)
