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
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from csv_export import csv_response
from database import get_db
from sorting import apply_sort
from models import (
    DocumentReference,
    DocumentStatus,
    DocumentType,
    DocumentTypeConfig,
    DocumentTypeRule,
    DocumentVersion,
    PartnerDocument,
    PartnerOrganization,
    User,
)
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(prefix="/partners", tags=["partner-documents"])

PROOF_OF_DOMICILE_MAX_AGE_DAYS = 90
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap (AD-37 -- size gate replaces type allowlist; 26214400 bytes)

# Document-type vocabulary mode -- when the document_types config table is
# empty, fall back to the legacy DocumentType enum so deploys remain robust
# pre-migration-017. Quote acceptance documents are routed through the same
# endpoint with document_type='quote_acceptance' -- pre-seed accepted there.
_QUOTE_DOC_TYPES = {"quote_acceptance", "purchase_order", "signed_proposal"}


def _find_rule_for_type(db: Session, document_type) -> Optional[DocumentTypeRule]:
    """Look up a ``document_type_rules`` row, matching case-insensitively
    and ignoring surrounding whitespace.

    FPRM-386 -- the Program Config -> Document Rules form is a free-text
    input, so an admin can persist a rule as ``"NDA"`` while uploads send
    the canonical lowercase code ``"nda"``. An exact ``==`` match silently
    misses, the upload falls through to the auto-approve default, and a
    ``requires_approval`` document is wrongly approved. Normalising both
    sides honours admin intent regardless of casing and repairs existing
    mis-cased rows immediately, with no data migration.
    """
    if document_type is None:
        return None
    key = str(document_type).strip().lower()
    if not key:
        return None
    return (
        db.query(DocumentTypeRule)
        .filter(func.lower(func.trim(DocumentTypeRule.document_type)) == key)
        .first()
    )


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

    # Sprint 22 / FPRM-371 -- enrich each row with the uploader's display
    # name. Single round-trip via IN clause; falls back to email when the
    # User has no full_name. None when the FK is null (historical rows).
    uploader_ids = {d.uploaded_by_user_id for d in docs if d.uploaded_by_user_id}
    uploader_map: dict = {}
    if uploader_ids:
        for u in db.query(User).filter(User.id.in_(uploader_ids)).all():
            uploader_map[u.id] = getattr(u, "full_name", None) or u.email
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

    items = []
    for d in docs:
        item = _serialize(d)
        item["uploaded_by_name"] = (
            uploader_map.get(d.uploaded_by_user_id) if d.uploaded_by_user_id else None
        )
        items.append(item)
    return {"items": items}


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
                detail="File too large. Maximum upload size is 25 MB.",
            )

    requested_code = str(payload["document_type"])
    if requested_code in _QUOTE_DOC_TYPES:
        # Quote-evidence vocabulary lives outside the document_types config
        # table (the table seeds compliance categories only). Accept the
        # value as-is so the centralised endpoint covers both flows.
        doc_type_value = requested_code
    else:
        # Sprint 22 -- admin-defined types via document_type_rules count
        # as valid. This unlocks Program Config -> Document Rules as the
        # canonical onboarding path for new document categories.
        # FPRM-386 -- match case-insensitively + trimmed (see
        # _find_rule_for_type) so a free-text rule entered as "NDA" still
        # validates an upload of "nda".
        rule_match = _find_rule_for_type(db, requested_code)
        if rule_match is not None:
            doc_type_value = rule_match.document_type
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
                detail="File too large. Maximum upload size is 25 MB.",
            )
    persisted_size = declared_size if declared_size is not None else decoded_size

    # Sprint 22 / AD-34 + FPRM-384 -- derive the initial status from the
    # document_type_rules table:
    #   * rule with auto_approve=true      -> approved
    #   * rule with requires_approval=true -> pending_review
    #   * no matching rule                 -> approved (default is
    #     auto-approve; routine attachments with no governing rule should
    #     not need a manual rubber-stamp)
    # FPRM-386 -- the lookup is case-insensitive + trimmed so a rule stored
    # with different casing than the upload's document_type is still found
    # and its requires_approval gate is honoured.
    rule = _find_rule_for_type(db, doc_type_value)
    if rule is None:
        initial_status = DocumentStatus.approved
    elif rule.auto_approve:
        initial_status = DocumentStatus.approved
    elif rule.requires_approval:
        initial_status = DocumentStatus.pending_review
    else:
        initial_status = DocumentStatus.approved

    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_id,
        document_type=doc_type_value,
        document_name=payload["document_name"],
        file_path=file_path,
        # Sprint 22 / AD-34 -- partner_documents.file_data is deprecated.
        # New uploads write to document_versions only.
        file_data=None,
        file_size_bytes=persisted_size,
        mime_type=payload.get("mime_type"),
        uploaded_by_user_id=current_user.id,
        expiry_date=expiry_value,
        status=initial_status,
        current_version_number=1 if file_data else None,
        version_count=1,
    )
    db.add(doc)
    db.flush()

    # Create initial version row when file_data was provided. Legacy
    # file_path-only uploads (still accepted for backward compat with the
    # AD-33 transition) skip the version row -- there are no bytes to
    # store yet.
    if file_data:
        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc.id,
            version_number=1,
            file_data=file_data,
            file_size_bytes=persisted_size,
            mime_type=payload.get("mime_type"),
            uploaded_by=current_user.id,
            is_current=True,
        )
        db.add(version)

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

    Sprint 22 / AD-34 -- reads from ``document_versions`` where
    ``is_current = true`` instead of the deprecated
    ``partner_documents.file_data`` column. Legacy rows uploaded before
    migration 037 fall back to ``partner_documents.file_data`` since the
    backfill copied that into a v1 row only when ``file_data IS NOT
    NULL`` -- the fallback path stays intact for the file_path-only
    legacy uploads from the Sprint 21 transition.

    Tenant isolation is enforced via ``_ensure_partner_exists_and_tenant``
    and the FK match in ``_load_doc_or_404`` -- two checks because losing
    either one is a hard data-leak (SOC II / ISO 27001 boundary).
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    current = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.is_current.is_(True),
        )
        .first()
    )
    raw_b64 = current.file_data if current else doc.file_data
    if not raw_b64:
        raise HTTPException(
            status_code=404,
            detail="No binary content stored for this document",
        )
    try:
        body = base64.b64decode(raw_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=500, detail="Stored document is corrupt")

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_document.download",
        object_type="partner_document",
        object_id=doc.id,
        after={
            "document_name": doc.document_name,
            "version_number": current.version_number if current else None,
        },
        ip_address=_client_ip(request),
    )

    safe_name = (doc.document_name or "document").replace('"', "")
    mime = (current.mime_type if current else None) or doc.mime_type or "application/octet-stream"
    return Response(
        content=body,
        media_type=mime,
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
    """Delete a partner document.

    Two paths converge here:

    1. **Internal hard-delete** (``channel_ops_admin`` / ``system_admin``):
       removes the partner_document row + every ``document_references``
       row pointing at it. Used to scrub evidence that should never have
       been uploaded.
    2. **Partner self-service delete** (``partner_admin`` own org,
       Sprint 22 / FPRM-370, fixed FPRM-383): allowed ONLY when zero
       document_references point at the document. Permanently removes the
       partner_document row -- the ``document_versions`` rows cascade away
       (FK ``ondelete=CASCADE`` + ORM ``cascade="all, delete-orphan"``).
       If any reference exists, returns 409 so the partner removes the
       attachment first.
    """
    role = UserRole(current_user.role)
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)
    snapshot = jsonable_encoder(_serialize(doc))

    if role == UserRole.partner_admin:
        ref_count = (
            db.query(DocumentReference)
            .filter(DocumentReference.document_id == doc.id)
            .count()
        )
        if ref_count > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Document is attached to one or more quotes and cannot "
                    "be deleted. Remove it from all quotes first."
                ),
            )
        # FPRM-383 -- permanently delete the unreferenced document instead
        # of soft-flagging it as rejected. Version rows cascade away.
        db.delete(doc)
        db.commit()
        log_audit_event(
            db=db,
            actor=current_user,
            action="document.deleted_by_partner",
            object_type="partner_document",
            object_id=doc_id,
            before=snapshot,
            ip_address=_client_ip(request),
        )
        return {"deleted": True, "id": str(doc_id)}

    if role not in _DELETE_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: channel_ops_admin or system_admin required",
        )

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



# ============================================================
# Sprint 22 / AD-34 -- Document versioning endpoints
# ============================================================


def _serialize_version(version: DocumentVersion, uploader_map: Optional[dict] = None) -> dict:
    """Version metadata without the binary blob.

    FPRM-390 (#1) -- ``uploaded_by_name`` is the uploader's display name
    (full_name, falling back to email) resolved from ``uploader_map`` so the
    version-history panel can show who uploaded each version. None when the
    FK is null or the map is absent.
    """
    uploaded_by_name = None
    if uploader_map and version.uploaded_by is not None:
        uploaded_by_name = uploader_map.get(version.uploaded_by)
    return {
        "id": str(version.id),
        "document_id": str(version.document_id),
        "version_number": version.version_number,
        "file_size_bytes": version.file_size_bytes,
        "mime_type": version.mime_type,
        "uploaded_by": str(version.uploaded_by) if version.uploaded_by else None,
        "uploaded_by_name": uploaded_by_name,
        "uploaded_at": version.uploaded_at.isoformat() if version.uploaded_at else None,
        "notes": version.notes,
        "is_current": bool(version.is_current),
    }


@router.post("/{partner_id}/documents/{doc_id}/versions", status_code=201)
def upload_new_version(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a new version of an existing document.

    Atomically demotes the prior current version and inserts the new one
    at ``max(version_number) + 1``. Updates the denormalised pointers on
    ``partner_documents`` so list views stay coherent.

    Approval workflow (AD-34 / FPRM-353 corollary):
        * If a ``document_type_rules`` row says ``requires_approval =
          true`` and ``auto_approve = false``, the new version resets
          ``partner_documents.status`` back to ``pending_review`` -- a
          revised contract isn't approved just because the original was.
        * If the rule says ``auto_approve = true``, status stays approved.
        * No rule => safe default: reset to ``pending_review``.
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    file_data = payload.get("file_data")
    if not isinstance(file_data, str) or not file_data:
        raise HTTPException(status_code=422, detail="file_data (base64) is required")
    try:
        decoded = base64.b64decode(file_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="file_data is not valid base64")
    if len(decoded) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail="File too large. Maximum upload size is 25 MB.",
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
                detail="File too large. Maximum upload size is 25 MB.",
            )
    persisted_size = declared_size if declared_size is not None else len(decoded)

    notes = payload.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise HTTPException(status_code=422, detail="notes must be a string")

    # Atomic version flip: demote prior current, find next version_number,
    # insert new row with is_current=True. Wrapped in a single flush
    # before commit so a failure on the insert leaves the prior version
    # current.
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.is_current.is_(True),
    ).update({"is_current": False}, synchronize_session=False)

    max_row = (
        db.query(DocumentVersion.version_number)
        .filter(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    next_version = (max_row[0] if max_row else 0) + 1

    new_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=next_version,
        file_data=file_data,
        file_size_bytes=persisted_size,
        mime_type=payload.get("mime_type"),
        uploaded_by=current_user.id,
        notes=notes,
        is_current=True,
    )
    db.add(new_version)

    doc.current_version_number = next_version
    doc.version_count = (doc.version_count or 0) + 1

    # FPRM-387 (#7 universal gate) -- resolve the rule via the shared
    # case-insensitive + trimmed helper so the version-upload path honours
    # the same matching as the initial upload.
    rule = _find_rule_for_type(db, doc.document_type)
    if rule and rule.auto_approve:
        doc.status = DocumentStatus.approved
    elif rule and rule.requires_approval:
        doc.status = DocumentStatus.pending_review
        doc.reviewed_at = None
        doc.reviewed_by_user_id = None
    else:
        doc.status = DocumentStatus.pending_review
        doc.reviewed_at = None
        doc.reviewed_by_user_id = None

    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document.version_uploaded",
        object_type="partner_document",
        object_id=doc.id,
        after={
            "version_number": next_version,
            "version_count": doc.version_count,
            "status": getattr(doc.status, "value", str(doc.status)),
        },
        ip_address=_client_ip(request),
    )
    return _serialize(doc)


@router.get("/{partner_id}/documents/{doc_id}/versions")
def list_document_versions(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Version history -- ordered newest first. ``file_data`` is never
    returned; clients fetch bytes via the per-version download endpoint."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    _load_doc_or_404(db, partner_id, doc_id)
    rows = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )
    # FPRM-390 (#1) -- resolve uploader display names in one round-trip so each
    # version row can show who uploaded it (full_name, falling back to email).
    uploader_ids = {v.uploaded_by for v in rows if v.uploaded_by}
    uploader_map: dict = {}
    if uploader_ids:
        for u in db.query(User).filter(User.id.in_(uploader_ids)).all():
            uploader_map[u.id] = getattr(u, "full_name", None) or u.email
    return [_serialize_version(v, uploader_map) for v in rows]


@router.get("/{partner_id}/documents/{doc_id}/versions/{version_id}/download")
def download_specific_version(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a specific historical version. Tenant-scoped + double-check
    that the version belongs to the requested document so a guessed
    version_id can't pivot into another partner's vault."""
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc.id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    try:
        body = base64.b64decode(version.file_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=500, detail="Stored version is corrupt")

    log_audit_event(
        db=db,
        actor=current_user,
        action="document.version_downloaded",
        object_type="partner_document",
        object_id=doc.id,
        after={
            "version_number": version.version_number,
            "document_name": doc.document_name,
        },
        ip_address=_client_ip(request),
    )

    safe_name = (doc.document_name or "document").replace('"', "")
    mime = version.mime_type or doc.mime_type or "application/octet-stream"
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(body)),
        },
    )


_INTERNAL_REVERT_ROLES = {
    UserRole.channel_manager,
    UserRole.channel_ops_admin,
    UserRole.system_admin,
}


@router.post("/{partner_id}/documents/{doc_id}/versions/{version_id}/revert")
def revert_to_version(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Make a historical version current again.

    FPRM-390 / AD-36 (supersedes the Sprint 22 internal-only FPRM-374
    decision): internal roles OR ``partner_admin`` on their OWN org may
    revert. ``partner_user`` remains excluded. Tenant scope is enforced by
    ``_ensure_partner_exists_and_tenant`` (partner roles must match the
    URL's partner_id), so a partner_admin can never revert another org's
    document.

    The previous current version is NOT deleted -- both rows survive so
    the audit trail captures every flip."""
    role = UserRole(current_user.role)
    if role not in _INTERNAL_REVERT_ROLES and role != UserRole.partner_admin:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: internal role or partner_admin (own org) required to revert versions",
        )
    # Enforces partner own-org boundary for partner_admin (403 on mismatch);
    # internal roles pass through.
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    target = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc.id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")

    from_version = doc.current_version_number

    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.is_current.is_(True),
    ).update({"is_current": False}, synchronize_session=False)
    target.is_current = True
    doc.current_version_number = target.version_number
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document.version_reverted",
        object_type="partner_document",
        object_id=doc.id,
        before={"from_version": from_version},
        after={"to_version": target.version_number},
        ip_address=_client_ip(request),
    )
    return _serialize(doc)


# ============================================================
# Sprint 22 -- Preview endpoint (Story 3 / FPRM-369)
# ============================================================


PREVIEWABLE_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
}


@router.get("/{partner_id}/documents/{doc_id}/preview")
def preview_document(
    partner_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """In-browser preview of the current version.

    For PDF + common image types, returns ``Content-Disposition: inline``
    so the browser renders rather than downloads. Anything else falls
    back to attachment disposition.

    Same tenant guard chain as download.
    """
    _ensure_partner_exists_and_tenant(db, partner_id, current_user)
    doc = _load_doc_or_404(db, partner_id, doc_id)

    current = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.is_current.is_(True),
        )
        .first()
    )
    raw_b64 = current.file_data if current else doc.file_data
    if not raw_b64:
        raise HTTPException(status_code=404, detail="No binary content for this document")
    try:
        body = base64.b64decode(raw_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=500, detail="Stored document is corrupt")

    mime = (current.mime_type if current else None) or doc.mime_type or "application/octet-stream"
    disposition = "inline" if mime in PREVIEWABLE_MIME_TYPES else "attachment"

    log_audit_event(
        db=db,
        actor=current_user,
        action="document.previewed",
        object_type="partner_document",
        object_id=doc.id,
        after={"mime_type": mime, "disposition": disposition},
        ip_address=_client_ip(request),
    )

    safe_name = (doc.document_name or "document").replace('"', "")
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            "Content-Length": str(len(body)),
        },
    )


# ============================================================
# Sprint 22 -- Document type rules CRUD (Story 2 / FPRM-366)
# ============================================================


_RULES_READ_ROLES = {
    UserRole.channel_manager,
    UserRole.channel_ops_admin,
    UserRole.system_admin,
}
_RULES_WRITE_ROLE = UserRole.system_admin


def _serialize_rule(rule: DocumentTypeRule) -> dict:
    return {
        "id": str(rule.id),
        "document_type": rule.document_type,
        "requires_approval": bool(rule.requires_approval),
        "auto_approve": bool(rule.auto_approve),
        "description": rule.description,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


rules_router = APIRouter(prefix="/admin/document-type-rules", tags=["document-type-rules"])


@rules_router.get("")
def list_document_type_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) not in _RULES_READ_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")
    rows = (
        db.query(DocumentTypeRule)
        .order_by(DocumentTypeRule.document_type)
        .all()
    )
    return [_serialize_rule(r) for r in rows]


@rules_router.post("", status_code=201)
def create_document_type_rule(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) != _RULES_WRITE_ROLE:
        raise HTTPException(status_code=403, detail="Only system_admin can create rules")
    doc_type = (payload.get("document_type") or "").strip()
    if not doc_type:
        raise HTTPException(status_code=422, detail="document_type is required")
    requires_approval = bool(payload.get("requires_approval", True))
    auto_approve = bool(payload.get("auto_approve", False))
    if auto_approve:
        requires_approval = False

    # FPRM-386 -- duplicate check is case-insensitive so "NDA" and "nda"
    # can't both exist; case-insensitive upload matching would otherwise be
    # ambiguous about which rule wins.
    existing = _find_rule_for_type(db, doc_type)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="A rule for this document type already exists",
        )

    rule = DocumentTypeRule(
        id=uuid.uuid4(),
        document_type=doc_type,
        requires_approval=requires_approval,
        auto_approve=auto_approve,
        description=payload.get("description"),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document_type_rule.created",
        object_type="document_type_rule",
        object_id=rule.id,
        after=_serialize_rule(rule),
        ip_address=_client_ip(request),
    )
    return _serialize_rule(rule)


@rules_router.patch("/{rule_id}")
def update_document_type_rule(
    rule_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) != _RULES_WRITE_ROLE:
        raise HTTPException(status_code=403, detail="Only system_admin can update rules")
    rule = db.query(DocumentTypeRule).filter(DocumentTypeRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    before = _serialize_rule(rule)

    if "requires_approval" in payload:
        rule.requires_approval = bool(payload["requires_approval"])
    if "auto_approve" in payload:
        rule.auto_approve = bool(payload["auto_approve"])
        if rule.auto_approve:
            rule.requires_approval = False
    if "description" in payload:
        rule.description = payload["description"]
    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        actor=current_user,
        action="document_type_rule.updated",
        object_type="document_type_rule",
        object_id=rule.id,
        before=before,
        after=_serialize_rule(rule),
        ip_address=_client_ip(request),
    )
    return _serialize_rule(rule)


@rules_router.delete("/{rule_id}", status_code=204)
def delete_document_type_rule(
    rule_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) != _RULES_WRITE_ROLE:
        raise HTTPException(status_code=403, detail="Only system_admin can delete rules")
    rule = db.query(DocumentTypeRule).filter(DocumentTypeRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    # FPRM-385 -- rules are freely deletable at any time. The previous
    # in-use 409 guard has been removed; existing partner_documents of this
    # type keep whatever status they received at upload (no cascade change).
    snapshot = _serialize_rule(rule)
    db.delete(rule)
    db.commit()

    log_audit_event(
        db=db,
        actor=current_user,
        action="document_type_rule.deleted",
        object_type="document_type_rule",
        object_id=rule_id,
        before=snapshot,
        ip_address=_client_ip(request),
    )
    return Response(status_code=204)
