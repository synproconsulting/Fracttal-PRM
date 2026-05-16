"""Partner activity endpoints (FPRM-57).

Notes, tasks, calls, meetings, emails, status-change events against a partner.
Partner-side users see only `is_internal = False` activities; internal users see all.

Permissions:
    GET    /partners/{partner_id}/activities                - any auth (tenant-scoped, is_internal filtered for partners)
    POST   /partners/{partner_id}/activities                - channel_manager+ (internal roles)
    PATCH  /partners/{partner_id}/activities/{activity_id}  - creator or channel_ops_admin
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import (
    ActivityType,
    PartnerActivity,
    PartnerOrganization,
    User,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partner-activities"])


def _serialize(a: PartnerActivity) -> dict:
    return {c.name: getattr(a, c.name) for c in a.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ensure_partner_and_tenant(db: Session, partner_id: uuid.UUID, current_user: User) -> None:
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{partner_id}/activities")
def list_activities(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_partner_and_tenant(db, partner_id, current_user)
    query = db.query(PartnerActivity).filter(PartnerActivity.partner_org_id == partner_id)
    if UserRole(current_user.role) in PARTNER_ROLES:
        query = query.filter(PartnerActivity.is_internal.is_(False))
    items = query.order_by(PartnerActivity.created_at.desc()).all()
    return {"items": [_serialize(a) for a in items]}


@router.post("/{partner_id}/activities", status_code=201)
def create_activity(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = UserRole(current_user.role)
    if role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")

    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    for required in ("activity_type", "title"):
        if required not in payload or not payload[required]:
            raise HTTPException(status_code=422, detail=f"{required} is required")

    try:
        atype = ActivityType(payload["activity_type"])
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid activity_type")

    activity = PartnerActivity(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        activity_type=atype,
        title=payload["title"],
        body=payload.get("body"),
        due_date=_parse_dt(payload.get("due_date")),
        assigned_to_user_id=_parse_uuid(payload.get("assigned_to_user_id")),
        is_internal=bool(payload.get("is_internal", True)),
        created_by_user_id=current_user.id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_activity.create",
        object_type="partner_activity",
        object_id=activity.id,
        after=jsonable_encoder(_serialize(activity)),
        ip_address=_client_ip(request),
    )
    return _serialize(activity)


@router.patch("/{partner_id}/activities/{activity_id}")
def update_activity(
    partner_id: uuid.UUID,
    activity_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = (
        db.query(PartnerActivity)
        .filter(PartnerActivity.id == activity_id, PartnerActivity.partner_org_id == partner_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    role = UserRole(current_user.role)
    is_creator = str(activity.created_by_user_id) == str(current_user.id)
    if not (is_creator or role in {UserRole.channel_ops_admin, UserRole.system_admin}):
        raise HTTPException(status_code=403, detail="Only the creator or channel_ops_admin may update")

    before = jsonable_encoder(_serialize(activity))
    mutable = {"title", "body", "due_date", "completed_at", "assigned_to_user_id", "is_internal"}
    for key, value in payload.items():
        if key not in mutable:
            continue
        if key in ("due_date", "completed_at"):
            setattr(activity, key, _parse_dt(value))
        elif key == "assigned_to_user_id":
            activity.assigned_to_user_id = _parse_uuid(value)
        else:
            setattr(activity, key, value)
    db.commit()
    db.refresh(activity)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_activity.update",
        object_type="partner_activity",
        object_id=activity.id,
        before=before,
        after=jsonable_encoder(_serialize(activity)),
        ip_address=_client_ip(request),
    )
    return _serialize(activity)


def _parse_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_uuid(value):
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
