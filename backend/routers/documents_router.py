"""Partner document endpoints (FPRM-55 + FPRM-108 activation hook).

Tracks legal/compliance documents required by the Fracttal Distributor Agreement.

Permissions:
    GET    /partners/{partner_id}/documents             - any auth (tenant-scoped)
    POST   /partners/{partner_id}/documents             - any auth (tenant-scoped); uploader = current_user
    PATCH  /partners/{partner_id}/documents/{doc_id}    - internal roles only (status/review)

Sprint 7 / FPRM-108: when an internal reviewer approves a document, we call
``recalculate_activation`` so the partner's checklist flips ``documents_uploaded``
once both required types (fiscal_id + id_legal_representative) are approved.
"""
import uuid
from datetime import date, datetime, timedelta

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from csv_export import csv_response
from database import get_db
from models import (
    DocumentType,
    DocumentTypeConfig,
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
    export: Optional[str] = Query(default=None),
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
    if export == "csv":
        partner = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.id == partner_id)
            .first()
        )
        partner_name = partner.legal_name if partner else ""
        reviewer_ids = {d.reviewed_by for d in docs if getattr(d, "reviewed_by", None)}
        reviewer_map = {}
        if reviewer_ids:
            for u in db.query(User).filter(User.id.in_(reviewer_ids)).all():
                reviewer_map[u.id] = u.email
        return csv_response(
            "documents_export",
            ["Partner Org", "Document Type", "Status", "Uploaded Date",
             "Reviewed Date", "Reviewer"],
            [
                [
                    partner_name,
                    getattr(d, "document_type", None).value if hasattr(getattr(d, "document_type", None), "value") else (d.document_type or ""),
                    getattr(d, "status", None).value if hasattr(getattr(d, "status", None), "value") else (d.status or ""),
                    d.uploaded_at.date().isoformat() if getattr(d, "uploaded_at", None) else "",
                    d.reviewed_at.date().isoformat() if getattr(d, "reviewed_at", None) else "",
                    reviewer_map.get(getattr(d, "reviewed_by", None), ""),
                ]
                for d in docs
            ],
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

    # FPRM-144: validate against the document_types config table rather than
    # the legacy Python enum. Falls back to the enum if no rows are present
    # (e.g. migration 017 not yet applied) so deploys remain robust.
    requested_code = str(payload["document_type"])
    config_count = db.query(DocumentTypeConfig).count()
    if config_count > 0:
        match = (
            db.query(DocumentTypeConfig)
            .filter(
                DocumentTypeConfig.code == requested_code,
                DocumentTypeConfig.is_active.is_(True),
            )
            .first()
        )
        if not match:
            raise HTTPException(status_code=422, detail="Invalid document_type")
        doc_type_value = match.code
    else:
        try:
            doc_type_value = DocumentType(requested_code).value
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

    if doc_type_value == "proof_of_fiscal_domicile" and expiry_value is not None:
        threshold = date.today() - timedelta(days=PROOF_OF_DOMICILE_MAX_AGE_DAYS)
        if expiry_value < threshold:
            raise HTTPException(
                status_code=422,
                detail="proof_of_fiscal_domicile is more than 3 months old",
            )

    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        document_type=doc_type_value,
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
    approved_now = False
    if "status" in payload:
        try:
            from models import DocumentStatus
            new_status = DocumentStatus(payload["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status value")
        if doc.status != new_status:
            doc.status = new_status
            status_changed = True
            doc.reviewed_by_user_id = current_user.id
            doc.reviewed_at = datetime.utcnow()
            if new_status == DocumentStatus.approved:
                approved_now = True
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

    # FPRM-108 — flip the partner's activation checklist when a required document
    # gets approved. Best-effort: a failure here must not roll back the review.
    if approved_now:
        try:
            from activation import recalculate_activation
            recalculate_activation(db, partner_id)
        except Exception:
            pass

    return _serialize(doc)
