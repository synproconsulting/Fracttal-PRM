"""Partner category + commission configuration (FPRM-58).

The `GET /config/partner-categories` endpoint is intentionally PUBLIC — it is
used by the partner registration form before the user has an account.

Permissions:
    GET    /config/partner-categories            - PUBLIC (no auth)
    POST   /config/partner-categories            - channel_ops_admin
    GET    /config/commission-structures         - any internal role
    PATCH  /config/commission-structures/{id}    - channel_ops_admin
"""
import uuid
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import (
    CommissionStructure,
    CommissionType,
    CommissionYear,
    DocumentTypeConfig,
    PartnerCategoryConfig,
    User,
)
from permissions import require_permission
from roles import INTERNAL_ROLES, UserRole

router = APIRouter(prefix="/config", tags=["config"])


def _serialize_category(c: PartnerCategoryConfig) -> dict:
    return {col.name: getattr(c, col.name) for col in c.__table__.columns}


def _serialize_commission(c: CommissionStructure) -> dict:
    return {col.name: getattr(c, col.name) for col in c.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/partner-categories")
def list_partner_categories(db: Session = Depends(get_db)):
    """Public endpoint — partner registration form consumes this."""
    cats = db.query(PartnerCategoryConfig).filter(PartnerCategoryConfig.is_active.is_(True)).all()
    return {"items": [_serialize_category(c) for c in cats]}


@router.post("/partner-categories", status_code=201)
def create_partner_category(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system_config:update_all")),
):
    for required in ("code", "display_name", "deal_reg_sla_hours", "max_discount_pct"):
        if required not in payload:
            raise HTTPException(status_code=422, detail=f"{required} is required")

    existing = db.query(PartnerCategoryConfig).filter(PartnerCategoryConfig.code == payload["code"]).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category code already exists")

    cat = PartnerCategoryConfig(
        id=uuid.uuid4(),
        code=payload["code"],
        display_name=payload["display_name"],
        description=payload.get("description"),
        deal_reg_sla_hours=int(payload["deal_reg_sla_hours"]),
        max_discount_pct=Decimal(str(payload["max_discount_pct"])),
        monthly_fee_usd=Decimal(str(payload.get("monthly_fee_usd", 200))),
        is_active=payload.get("is_active", True),
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_category_config.create",
        object_type="partner_category_config",
        object_id=cat.id,
        after=jsonable_encoder(_serialize_category(cat)),
        ip_address=_client_ip(request),
    )
    return _serialize_category(cat)


@router.get("/commission-structures")
def list_commission_structures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")
    rows = db.query(CommissionStructure).all()
    return {"items": [_serialize_commission(r) for r in rows]}


@router.patch("/commission-structures/{cs_id}")
def update_commission_structure(
    cs_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system_config:update_all")),
):
    cs = db.query(CommissionStructure).filter(CommissionStructure.id == cs_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Commission structure not found")

    before = jsonable_encoder(_serialize_commission(cs))

    if "commission_pct" in payload:
        cs.commission_pct = Decimal(str(payload["commission_pct"]))
    if "subpartner_uplift_pct" in payload:
        cs.subpartner_uplift_pct = Decimal(str(payload["subpartner_uplift_pct"]))
    if "applies_to_upsell" in payload:
        cs.applies_to_upsell = bool(payload["applies_to_upsell"])
    if "notes" in payload:
        cs.notes = payload["notes"]

    db.commit()
    db.refresh(cs)

    log_audit_event(
        db=db,
        actor=current_user,
        action="commission_structure.update",
        object_type="commission_structure",
        object_id=cs.id,
        before=before,
        after=jsonable_encoder(_serialize_commission(cs)),
        ip_address=_client_ip(request),
    )
    return _serialize_commission(cs)


# -------------------- Document type config (Sprint 9 / FPRM-144) --------------------


def _serialize_document_type(d: DocumentTypeConfig) -> dict:
    return {col.name: getattr(d, col.name) for col in d.__table__.columns}


@router.get("/document-types")
def list_document_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """Public endpoint — upload forms and validation both consume this.

    By default returns only active types. Pass ``?include_inactive=true`` to
    include archived types (e.g. for admin tooling that lists all).
    """
    q = db.query(DocumentTypeConfig)
    if not include_inactive:
        q = q.filter(DocumentTypeConfig.is_active.is_(True))
    rows = q.order_by(DocumentTypeConfig.label.asc()).all()
    return {"items": [_serialize_document_type(r) for r in rows]}


@router.post("/document-types", status_code=201)
def create_document_type(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system_config:update_all")),
):
    """Create a new document type vocabulary entry. system_admin / channel_ops_admin only."""
    code = (payload.get("code") or "").strip()
    label = (payload.get("label") or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    if not label:
        raise HTTPException(status_code=422, detail="label is required")

    existing = db.query(DocumentTypeConfig).filter(DocumentTypeConfig.code == code).first()
    if existing:
        raise HTTPException(status_code=409, detail="document_type code already exists")

    row = DocumentTypeConfig(
        id=uuid.uuid4(),
        code=code,
        label=label,
        is_active=bool(payload.get("is_active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document_type.create",
        object_type="document_type",
        object_id=row.id,
        after=jsonable_encoder(_serialize_document_type(row)),
        ip_address=_client_ip(request),
    )
    return _serialize_document_type(row)


@router.patch("/document-types/{dt_id}")
def update_document_type(
    dt_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system_config:update_all")),
):
    """Update label / is_active for a document type. ``code`` is immutable."""
    row = db.query(DocumentTypeConfig).filter(DocumentTypeConfig.id == dt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="document_type not found")

    before = jsonable_encoder(_serialize_document_type(row))
    if "label" in payload:
        new_label = (payload["label"] or "").strip()
        if not new_label:
            raise HTTPException(status_code=422, detail="label cannot be empty")
        row.label = new_label
    if "is_active" in payload:
        row.is_active = bool(payload["is_active"])
    db.commit()
    db.refresh(row)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document_type.update",
        object_type="document_type",
        object_id=row.id,
        before=before,
        after=jsonable_encoder(_serialize_document_type(row)),
        ip_address=_client_ip(request),
    )
    return _serialize_document_type(row)
