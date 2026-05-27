"""Centralised partner document repository (AD-33).

Sprint 21 / FPRM-AD33 makes ``partner_documents`` the single source of truth
for every partner-scoped file. Quote acceptance evidence, compliance docs,
NDA scans, future deal attachments -- all live here, with cross-record
links recorded in ``document_references``.

Permissions
-----------
GET    /partners/{partner_id}/documents                       any authenticated user; tenant-scoped
POST   /partners/{partner_id}/documents                       any authenticated user; tenant-scoped
GET    /partners/{partner_id}/documents/{doc_id}              tenant-scoped read of one doc (metadata only)
GET    /partners/{partner_id}/documents/{doc_id}/download     stream the raw bytes (AD-20)
PATCH  /partners/{partner_id}/documents/{doc_id}              internal roles only -- review/approve
DELETE /partners/{partner_id}/documents/{doc_id}              system_admin / channel_ops_admin only
GET    /partners/{partner_id}/documents/{doc_id}/references   list cross-record links
POST   /partners/{partner_id}/documents/{doc_id}/references   create a new link
DELETE /partners/{partner_id}/documents/{doc_id}/references/{ref_id}  remove a link

``file_data`` is never returned by the list / metadata / patch endpoints --
binary content goes through the dedicated download route. Tenant isolation
on ``partner_org_id`` is enforced on every read / write path without
exception (SOC II / ISO 27001 boundary per AD-33).
"""
import base64
import binascii
import uuid
from datetime import date, datetime, timedelta

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from csv_export import csv_response
from database import get_db
from sorting import apply_sort
from models import (
    DocumentReference,
    DocumentType,
    DocumentTypeConfig,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partner-documents"])

PROOF_OF_DOMICILE_MAX_AGE_DAYS = 90
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB cap (matches retired quote_documents)

# Document-type vocabulary mode -- when the document_types config table is
# empty, fall back to the legacy DocumentType enum so deploys remain robust
# pre-migration-017. Quote acceptance documents are routed through the same
# endpoint with document_type='quote_acceptance' -- pre-seed accepted there.
_QUOTE_DOC_TYPES = {"quote_acceptance", "purchase_order", "signed_proposal"}


def _doc_columns_excluding_data() -> list[str]:
    """Column allow-list for serialised payloads.

    ``file_data`` is the binary blob and must NEVER appear in list /
    metadata / patch responses -- only the dedicated download endpoint
    streams those bytes. Centralising the allow-list here closes a class
    of leak bugs where a future column rename or a forgotten ``del`` would
    silently re-expose the data.
    """
    return [
        c.name for c in PartnerDocument.__table__.columns if c.name != "file_data"
    ]


def _serialize(doc: PartnerDocument) -> dict:
    return {c: getattr(doc, c) for c in _doc_columns_excluding_data()}


def _serialize_reference(ref: DocumentReference) -> dict:
    return {
        "id": str(ref.id),
        "document_id": str(ref.document_id),
        "entity_type": ref.entity_type,
        "entity_id": str(ref.entity_id),
        "label": ref.label,
        "created_at": ref.created_at.isoformat() if ref.created_at else None,
    }


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def _ensure_partner_exists_and_tenant(
    db: Session, partner_id: uuid.UUID, current_user: User
) -> None:
    partner = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == partner_id)
        .first()
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    if UserRole(current_user.role) in PARTNER_ROLES:
        if current_user.partner_org_id is None or str(current_user.partner_org_id) != str(partner_id):
            raise HTTPException(status_code=403, detail="Access denied")


def _load_doc_or_404(
    db: Session, partner_id: uuid.UUID, doc_id: uuid.UUID
) -> PartnerDocument:
    """Load a partner_documents row, enforcing the partner_org_id boundary.

    Per AD-33 the partner_org_id on the row MUST equal the partner_id from
    the URL. Mismatches return 404 (rather than 403) so an attacker cannot
    infer the existence of a foreign document.
    """
    doc = (
        db.query(PartnerDocument)
        .filter(
            PartnerDocument.id == doc_id,
            PartnerDocument.partner_org_id == partner_id,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


_DOCUMENT_SORT = {
    "document_type": PartnerDocument.document_type,
    "status": PartnerDocument.status,
    "created_at": PartnerDocument.uploaded_at,
}


@router.get("/{partner_id}/documents")
def list_documents(
    partner_id: uuid.UUID,
    export: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    document_type: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_dir: Optional[str] = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List partner documents (tenant-scoped). ``file_data`` is omitted from
    every row -- binary content lives only on the download endpoint."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    query = (
        db.query(PartnerDocument)
        .filter(PartnerDocument.partner_org_id == partner_id)
    )
    if status:
        query = query.filter(PartnerDocument.status == status)
    if document_type:
        query = query.filter(PartnerDocument.document_type == document_type)
    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed=_DOCUMENT_SORT,
        default_col=PartnerDocument.uploaded_at,
        tiebreaker=PartnerDocument.id,
    )
    docs = query.all()
    if export == "csv":
        partner = (
            db.query(PartnerOrganization)
            .filter(PartnerOrganization.id == partner_id)
            .first()
        )
        partner_name = partner.legal_name if partner else ""
        reviewer_ids = {
            d.reviewed_by_user_id for d in docs if getattr(d, "reviewed_by_user_id", None)
        }
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
                    getattr(d.document_type, "value", d.document_type) or "",
                    getattr(d.status, "value", d.status) or "",
                    d.uploaded_at.date().isoformat() if d.uploaded_at else "",
                    d.reviewed_at.date().isoformat() if d.reviewed_at else "",
                    reviewer_map.get(d.reviewed_by_user_id, ""),
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
    """Upload a partner document.

    Centralised body (Sprint 21 / AD-33):
        document_type    -- required, validated against document_types
                            config OR quote-doc vocabulary
        document_name    -- required
        file_data        -- base64-encoded bytes (preferred path)
        file_path        -- legacy on-disk path (still accepted)
        file_size_bytes  -- optional but recommended; cross-checked against
                            decoded file_data when present
        mime_type        -- optional
        expiry_date      -- optional ISO date (used by proof-of-domicile
                            staleness gate)
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)

    for required in ("document_type", "document_name"):
        if required not in payload or not payload[required]:
            raise HTTPException(status_code=422, detail=f"{required} is required")

    file_data = payload.get("file_data")
    file_path = payload.get("file_path")
    if not file_data and not file_path:
        raise HTTPException(
            status_code=422,
            detail="Either file_data (base64) or file_path is required",
        )

    decoded_size: Optional[int] = None
    if file_data:
        if not isinstance(file_data, str):
            raise HTTPException(
                status_code=422, detail="file_data must be a base64 string",
            )
        try:
            decoded = base64.b64decode(file_data, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=422, detail="file_data is not valid base64")
        decoded_size = len(decoded)
        if decoded_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=422,
                detail="File too large. Maximum upload size is 10 MB.",
            )

    requested_code = str(payload["document_type"])
    if requested_code in _QUOTE_DOC_TYPES:
        # Quote-evidence vocabulary lives outside the document_types config
        # table (the table seeds compliance categories only). Accept the
        # value as-is so the centralised endpoint covers both flows.
        doc_type_value = requested_code
    else:
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

    declared_size = payload.get("file_size_bytes")
    if declared_size is not None:
        if not isinstance(declared_size, int) or declared_size < 0:
            raise HTTPException(
                status_code=422, detail="file_size_bytes must be a non-negative integer",
            )
        if declared_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=422,
                detail="File too large. Maximum upload size is 10 MB.",
            )
    persisted_size = declared_size if declared_size is not None else decoded_size

    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        document_type=doc_type_value,
        document_name=payload["document_name"],
        file_path=file_path,
        file_data=file_data,
        file_size_bytes=persisted_size,
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


@router.get("/{partner_id}/documents/{doc_id}")
def get_document_metadata(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return one document's metadata. ``file_data`` is omitted."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)
    return _serialize(doc)


@router.get("/{partner_id}/documents/{doc_id}/download")
def download_document(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the document's binary content (AD-20).

    Tenant isolation is enforced via ``_ensure_partner_exists_and_tenant``
    and the FK match in ``_load_doc_or_404`` -- two checks because losing
    either one is a hard data-leak (SOC II / ISO 27001 boundary).
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)
    if not doc.file_data:
        raise HTTPException(
            status_code=404,
            detail="No binary content stored for this document",
        )
    try:
        body = base64.b64decode(doc.file_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=500, detail="Stored document is corrupt")

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.download",
        object_type="partner_document",
        object_id=doc.id,
        after={"document_name": doc.document_name},
        ip_address=_client_ip(request),
    )

    safe_name = (doc.document_name or "document").replace('"', "")
    return Response(
        content=body,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(body)),
        },
    )


@router.patch("/{partner_id}/documents/{doc_id}")
def review_document(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Internal review (approve / reject / set notes / update expiry)."""
    role = UserRole(current_user.role)
    if role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required to review documents")

    doc = _load_doc_or_404(db, partner_id, doc_id)

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

    if approved_now:
        try:
            from activation import recalculate_activation
            recalculate_activation(db, partner_id)
        except Exception:
            pass

    return _serialize(doc)


_DELETE_ROLES = {UserRole.channel_ops_admin, UserRole.system_admin}


@router.delete("/{partner_id}/documents/{doc_id}")
def delete_document(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hard-delete a partner document and every reference pointing at it.

    Auth: ``channel_ops_admin`` or ``system_admin`` only. Documents are
    evidence so the bar is intentionally higher than upload.
    """
    if UserRole(current_user.role) not in _DELETE_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: channel_ops_admin or system_admin required",
        )
    doc = _load_doc_or_404(db, partner_id, doc_id)
    snapshot = jsonable_encoder(_serialize(doc))
    db.query(DocumentReference).filter(
        DocumentReference.document_id == doc.id
    ).delete(synchronize_session=False)
    db.delete(doc)
    db.commit()
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.deleted",
        object_type="partner_document",
        object_id=doc_id,
        before=snapshot,
        ip_address=_client_ip(request),
    )
    return {"deleted": True, "id": str(doc_id)}


# ============================ Document references ============================


@router.get("/{partner_id}/documents/{doc_id}/references")
def list_document_references(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List every cross-record link pointing at this document."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    _load_doc_or_404(db, partner_id, doc_id)
    refs = (
        db.query(DocumentReference)
        .filter(DocumentReference.document_id == doc_id)
        .order_by(DocumentReference.created_at.desc())
        .all()
    )
    return [_serialize_reference(r) for r in refs]


@router.post("/{partner_id}/documents/{doc_id}/references", status_code=201)
def create_document_reference(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach this document to another workflow object.

    Body:
        entity_type  -- ``quote`` | ``quote_version`` | ``deal`` | ...
        entity_id    -- UUID of the target object
        label        -- semantic tag (e.g. ``quote_acceptance``)
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    entity_type = (payload.get("entity_type") or "").strip()
    if not entity_type:
        raise HTTPException(status_code=422, detail="entity_type is required")
    entity_id_raw = payload.get("entity_id")
    if not entity_id_raw:
        raise HTTPException(status_code=422, detail="entity_id is required")
    try:
        entity_id = uuid.UUID(str(entity_id_raw))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="entity_id must be a UUID")
    label = payload.get("label")
    if label is not None and not isinstance(label, str):
        raise HTTPException(status_code=422, detail="label must be a string")

    ref = DocumentReference(
        id=uuid.uuid4(),
        document_id=doc.id,
        entity_type=entity_type,
        entity_id=entity_id,
        label=label,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.reference_created",
        object_type="document_reference",
        object_id=ref.id,
        after={
            "document_id": str(doc.id),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "label": label,
        },
        ip_address=_client_ip(request),
    )
    return _serialize_reference(ref)


@router.delete("/{partner_id}/documents/{doc_id}/references/{ref_id}")
def delete_document_reference(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    ref_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a cross-record link without touching the underlying document."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    _load_doc_or_404(db, partner_id, doc_id)
    ref = (
        db.query(DocumentReference)
        .filter(
            DocumentReference.id == ref_id,
            DocumentReference.document_id == doc_id,
        )
        .first()
    )
    if ref is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    snapshot = _serialize_reference(ref)
    db.delete(ref)
    db.commit()
    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.reference_deleted",
        object_type="document_reference",
        object_id=ref_id,
        before=snapshot,
        ip_address=_client_ip(request),
    )
    return {"deleted": True, "id": str(ref_id)}
