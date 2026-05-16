"""Partner application endpoints (FPRM-75 / Sprint 5).

Public endpoints authenticate via a per-application ``draft_token`` query
parameter (issued at draft creation). Internal endpoints require a JWT
with the ``partner_application:read_all`` permission.

    POST   /applications                   public  create draft
    GET    /applications/{id}              public-with-draft_token OR internal-JWT
    PATCH  /applications/{id}              public-with-draft_token
    POST   /applications/{id}/submit       public-with-draft_token
    POST   /applications/{id}/documents    public-with-draft_token
    GET    /applications                   internal-JWT (channel_manager+)
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import decode_access_token
from audit import log_audit_event
from database import get_db
from models import (
    ApplicationStatus,
    PartnerApplication,
    PartnerApplicationDocument,
    User,
)
from permissions import has_permission, require_permission


router = APIRouter(prefix="/applications", tags=["applications"])


PUBLIC_WRITABLE_FIELDS = {
    "applicant_email", "applicant_name", "applicant_phone", "applicant_title",
    "legal_name", "dba_name", "website", "hq_address", "phone",
    "requested_categories", "territory", "industries",
    "year_established", "employee_count", "annual_revenue", "shareholders",
    "other_software_products", "cmms_experience", "cmms_experience_description",
    "sales_marketing_strategy", "technical_support_team", "technical_support_description",
    "implementation_services", "implementation_description",
    "partnership_goals", "market_growth_plan", "additional_info", "references",
    "terms_accepted",
}


def _serialize(app: PartnerApplication) -> dict:
    data = {c.name: getattr(app, c.name) for c in app.__table__.columns}
    return jsonable_encoder(data)


def _serialize_doc(doc: PartnerApplicationDocument) -> dict:
    return jsonable_encoder({c.name: getattr(doc, c.name) for c in doc.__table__.columns})


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _validate_draft_token(
    application_id: uuid.UUID,
    draft_token: str,
    db: Session,
) -> PartnerApplication:
    app_record = db.query(PartnerApplication).filter(PartnerApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app_record.draft_token or app_record.draft_token != draft_token:
        raise HTTPException(status_code=403, detail="Invalid draft token")
    if app_record.draft_expires_at and app_record.draft_expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Draft has expired")
    return app_record


def _user_from_bearer(authorization: Optional[str], db: Session) -> Optional[User]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user or not user.is_active:
        return None
    return user


@router.post("", status_code=201)
def create_draft(payload: dict, db: Session = Depends(get_db)):
    """Public endpoint - creates a draft application and returns id + draft_token."""
    applicant_email = (payload.get("applicant_email") or "").strip()
    if not applicant_email:
        raise HTTPException(status_code=422, detail="applicant_email is required")

    draft_token = uuid.uuid4().hex
    app_record = PartnerApplication(
        id=uuid.uuid4(),
        status=ApplicationStatus.draft,
        applicant_email=applicant_email,
        draft_token=draft_token,
        draft_expires_at=datetime.utcnow() + timedelta(days=30),
    )
    for key, value in payload.items():
        if key in PUBLIC_WRITABLE_FIELDS and key != "applicant_email":
            setattr(app_record, key, value)

    db.add(app_record)
    db.commit()
    db.refresh(app_record)
    return {"id": str(app_record.id), "draft_token": app_record.draft_token}


@router.get("")
def list_applications(
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Internal endpoint - paginated list of applications, filterable by status."""
    query = db.query(PartnerApplication)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            query = query.filter(PartnerApplication.status.in_(statuses))
    total = query.count()
    items = (
        query.order_by(PartnerApplication.submitted_at.desc().nullslast() if hasattr(PartnerApplication.submitted_at.desc(), "nullslast") else PartnerApplication.submitted_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize(i) for i in items],
    }


@router.get("/{application_id}")
def get_application(
    application_id: uuid.UUID,
    draft_token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Public with ?draft_token=... OR internal with Bearer token (read_all)."""
    if draft_token:
        return _serialize(_validate_draft_token(application_id, draft_token, db))

    user = _user_from_bearer(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="draft_token or authentication required")
    if not has_permission(user.role, "partner_application:read_all"):
        raise HTTPException(status_code=403, detail="Permission denied: partner_application:read_all required")
    app_record = db.query(PartnerApplication).filter(PartnerApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize(app_record)


@router.patch("/{application_id}")
def update_draft(
    application_id: uuid.UUID,
    payload: dict,
    draft_token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Public draft update via draft_token."""
    app_record = _validate_draft_token(application_id, draft_token, db)
    if app_record.status not in (ApplicationStatus.draft, ApplicationStatus.info_required):
        raise HTTPException(status_code=400, detail="Application cannot be edited in current status")
    for key, value in payload.items():
        if key in PUBLIC_WRITABLE_FIELDS:
            setattr(app_record, key, value)
    app_record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)
    return _serialize(app_record)


@router.post("/{application_id}/submit")
def submit_application(
    application_id: uuid.UUID,
    request: Request,
    draft_token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Public submit via draft_token. Validates required fields then sets status=submitted."""
    app_record = _validate_draft_token(application_id, draft_token, db)
    if app_record.status not in (ApplicationStatus.draft, ApplicationStatus.info_required):
        raise HTTPException(status_code=400, detail="Application has already been submitted")

    errors = []
    if not (app_record.legal_name or "").strip():
        errors.append("legal_name is required")
    if not (app_record.applicant_email or "").strip():
        errors.append("applicant_email is required")
    if not (app_record.applicant_name or "").strip():
        errors.append("applicant_name is required")
    if not app_record.terms_accepted:
        errors.append("terms must be accepted")
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    before_status = app_record.status.value if hasattr(app_record.status, "value") else str(app_record.status)
    app_record.status = ApplicationStatus.submitted
    app_record.submitted_at = datetime.utcnow()
    app_record.terms_accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)

    log_audit_event(
        db=db,
        actor=None,
        action="partner_application.submitted",
        object_type="partner_application",
        object_id=app_record.id,
        before={"status": before_status},
        after={
            "status": "submitted",
            "applicant_email": app_record.applicant_email,
            "legal_name": app_record.legal_name,
        },
        ip_address=_client_ip(request),
    )

    return {
        "id": str(app_record.id),
        "status": app_record.status.value if hasattr(app_record.status, "value") else str(app_record.status),
        "submitted_at": app_record.submitted_at.isoformat() if app_record.submitted_at else None,
    }


@router.post("/{application_id}/documents", status_code=201)
def upload_document_metadata(
    application_id: uuid.UUID,
    payload: dict,
    draft_token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Record document metadata for a draft application. Actual file storage is TBD."""
    app_record = _validate_draft_token(application_id, draft_token, db)

    document_name = (payload.get("document_name") or "").strip()
    file_path = (payload.get("file_path") or "").strip()
    if not document_name or not file_path:
        raise HTTPException(status_code=422, detail="document_name and file_path are required")

    doc = PartnerApplicationDocument(
        id=uuid.uuid4(),
        application_id=app_record.id,
        document_type=(payload.get("document_type") or "other"),
        document_name=document_name,
        file_path=file_path,
        file_size_bytes=payload.get("file_size_bytes"),
        mime_type=payload.get("mime_type"),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _serialize_doc(doc)
