"""Partner document endpoints (FPRM-55).

Tracks legal/compliance documents required by the Fracttal Distributor Agreement.

Permissions:
    GET    /partners/{partner_id}/documents             - any auth (tenant-scoped)
    POST   /partners/{partner_id}/documents             - any auth (tenant-scoped); uploader = current_user
    PATCH  /partners/{partner_id}/documents/{doc_id}    - internal roles only (status/review)
"""
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import (
    DocumentType,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partner-documents"])

PROOF_OF_DOMICILE_MAX_AGE_DAYS = 90


def _serialize(doc: PartnerDocument) -> dict:
    return {c.name: getattr(doc, c.name) for c in doc.__table__.columns}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ensure_partner_exists_and_tenant(db: Session, partner_id: uuid.UUID, current_user: User) -> None:
    partner = db.query(PartnerOrganization).filter(PartnerOrganization.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{partner_id}/documents")
def list_documents(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    docs = (
        db.query(PartnerDocument)
        .filter(PartnerDocument.partner_org_id == partner_id)
        .order_by(PartnerDocument.uploaded_at.desc())
        .all()
    )
    return {"items": [_serialize(d) for d in docs]}


@router.post("/{partner_id}/documents", status_code=201)
def upload_document(
    partner_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)

    for required in ("document_type", "document_name", "file_path"):
        if required not in payload or not payload[required]:
            raise HTTPException(status_code=422, detail=f"{required} is required")

    try:
        doc_type = DocumentType(payload["document_type"])
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_type")

    expiry_str = payload.get("expiry_date")
    expiry_value: date | None = None
    if expiry_str:
        try:
            expiry_value = (
                expiry_str if isinstance(expiry_str, date) else date.fromisoformat(str(expiry_str))
            )
        except ValueError:
            raise HTTPException(status_code=422, detail="expiry_date must be ISO date (YYYY-MM-DD)")

    if doc_type == DocumentType.proof_of_fiscal_domicile and expiry_value is not None:
        threshold = date.today() - timedelta(days=PROOF_OF_DOMICILE_MAX_AGE_DAYS)
        if expiry_value < threshold:
            raise HTTPException(
                status_code=422,
                detail="proof_of_fiscal_domicile is more than 3 months old",
            )

    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        document_type=doc_type,
        document_name=payload["document_name"],
        file_path=payload["file_path"],
        file_size_bytes=payload.get("file_size_bytes"),
        mime_type=payload.get("mime_type"),
        uploaded_by_user_id=current_user.id,
        expiry_date=expiry_value,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.upload",
        object_type="partner_document",
        object_id=doc.id,
        after=jsonable_encoder(_serialize(doc)),
        ip_address=_client_ip(request),
    )
    return _serialize(doc)


@router.patch("/{partner_id}/documents/{doc_id}")
def review_document(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = UserRole(current_user.role)
    if role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required to review documents")

    doc = (
        db.query(PartnerDocument)
        .filter(PartnerDocument.id == doc_id, PartnerDocument.partner_org_id == partner_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    before = jsonable_encoder(_serialize(doc))
    status_changed = False
    if "status" in payload:
        try:
            from models import DocumentStatus  # local import to keep top tidy
            new_status = DocumentStatus(payload["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status value")
        if doc.status != new_status:
            doc.status = new_status
            status_changed = True
            doc.reviewed_by_user_id = current_user.id
            doc.reviewed_at = datetime.utcnow()
    if "review_notes" in payload:
        doc.review_notes = payload["review_notes"]
    if "expiry_date" in payload and payload["expiry_date"] is not None:
        try:
            doc.expiry_date = date.fromisoformat(str(payload["expiry_date"]))
        except ValueError:
            raise HTTPException(status_code=422, detail="expiry_date must be ISO date (YYYY-MM-DD)")

    db.commit()
    db.refresh(doc)

    action = "partner_document.status_change" if status_changed else "partner_document.update"
    log_audit_event(
        db=db,
        actor=current_user,
        action=action,
        object_type="partner_document",
        object_id=doc.id,
        before=before,
        after=jsonable_encoder(_serialize(doc)),
        ip_address=_client_ip(request),
    )
    return _serialize(doc)
