"""Partner organization CRUD endpoints.

Permissions:
    GET    /partners           - requires partner_organization:read_all (internal roles only)
    GET    /partners/{id}      - any authenticated user (partner-side users limited to own org)
    POST   /partners           - requires partner_organization:create (channel_ops_admin, system_admin)
    PATCH  /partners/{id}      - channel_ops_admin/system_admin (any) or partner_admin (own org only)
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import PartnerOrganization, User
from permissions import require_permission
from roles import PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partners"])


def _serialize(partner: PartnerOrganization) -> dict:
    return {c.name: getattr(partner, c.name) for c in partner.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("")
def list_partners(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_organization:read_all")),
):
    query = db.query(PartnerOrganization)
    total = query.count()
    items = query.order_by(PartnerOrganization.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize(p) for p in items],
    }


@router.get("/{partner_id}")
def get_partner(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner.id):
            raise HTTPException(status_code=403, detail="Access denied")
    return _serialize(partner)


@router.post("", status_code=201)
def create_partner(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_organization:create")),
):
    if "legal_name" not in payload or not payload["legal_name"]:
        raise HTTPException(status_code=422, detail="legal_name is required")
    if "program_type" not in payload:
        raise HTTPException(status_code=422, detail="program_type is required")
    if "partner_category" not in payload:
        raise HTTPException(status_code=422, detail="partner_category is required")
    try:
        partner = PartnerOrganization(**payload)
    except TypeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")
    db.add(partner)
    db.commit()
    db.refresh(partner)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_organization.create",
        object_type="partner_organization",
        object_id=partner.id,
        after=jsonable_encoder(_serialize(partner)),
        ip_address=_client_ip(request),
    )
    return _serialize(partner)


@router.patch("/{partner_id}")
def update_partner(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    role = UserRole(current_user.role)
    if role == UserRole.partner_admin:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner.id):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role not in {UserRole.channel_ops_admin, UserRole.system_admin}:
        raise HTTPException(status_code=403, detail="Insufficient permissions to update partner")

    before = jsonable_encoder(_serialize(partner))
    immutable = {"id", "created_at"}
    for key, value in payload.items():
        if key in immutable:
            continue
        if hasattr(partner, key):
            setattr(partner, key, value)
    partner.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(partner)
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_organization.update",
        object_type="partner_organization",
        object_id=partner.id,
        before=before,
        after=jsonable_encoder(_serialize(partner)),
        ip_address=_client_ip(request),
    )
    return _serialize(partner)
