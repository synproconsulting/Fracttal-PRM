"""Partner application endpoints (FPRM-75 / Sprint 5, extended in Sprint 6).

Public endpoints authenticate via a per-application ``draft_token`` query
parameter (issued at draft creation). Internal endpoints require a JWT
with the ``partner_application:read_all`` permission.

    POST   /applications                         public  create draft
    GET    /applications/{id}                    public-with-draft_token OR internal-JWT
    PATCH  /applications/{id}                    public-with-draft_token
    POST   /applications/{id}/submit             public-with-draft_token
    POST   /applications/{id}/documents          public-with-draft_token
    GET    /applications                         internal-JWT (channel_manager+)

Sprint 6 additions (FPRM-90):
    POST   /applications/{id}/approve            internal-JWT (channel_manager+)
    POST   /applications/{id}/reject             internal-JWT (channel_manager+)
    POST   /applications/{id}/request-info       internal-JWT (channel_manager+)
    GET    /applications/{id}/timeline           public-with-draft_token OR internal-JWT
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric
from sqlalchemy.orm import Session

from auth import get_optional_bearer_user
from audit import log_audit_event
from csv_export import csv_response
from database import get_db
from sorting import apply_sort
from models import (
    ApplicationMessageSender,
    ApplicationStatus,
    AuditLog,
    PartnerApplication,
    PartnerApplicationDocument,
    PartnerApplicationMessage,
    User,
)
from approval_helpers import (
    WORKFLOW_PARTNER_APPLICATION,
    build_approval_progress,
    get_approval_step_context,
    record_step_action,
)
from permissions import has_permission, require_permission
from rate_limiter import limiter
from notifications import (
    notify_application_approved,
    notify_application_rejected,
    notify_application_submitted,
    notify_info_required,
)


router = APIRouter(prefix="/applications", tags=["applications"])


# AD-44 (FPRM-455) — per-IP limit on the unauthenticated public application
# surface (create + draft writes). Read from env at request time so it is
# tunable in Railway without a redeploy; safe default applies when unset.
def _public_app_limit() -> str:
    return os.getenv("RATE_LIMIT_PUBLIC_APP", "20/minute")


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


# FPRM-464 — application columns where an empty string is an invalid value and
# must become NULL before the DB write. The public draft create/update endpoints
# accept a raw dict and ``setattr`` values directly, so an empty string from an
# unfilled numeric/boolean/date form field (e.g. ``year_established``) would
# otherwise crash on the Postgres commit. Derived from the model so any new
# non-text column is covered automatically.
_NON_STRING_APPLICATION_COLUMNS = frozenset(
    name
    for name, col in PartnerApplication.__table__.columns.items()
    if isinstance(col.type, (Integer, Numeric, Float, Boolean, Date, DateTime))
)


def _coerce_blank_to_none(payload: dict) -> None:
    """Mutate ``payload`` in place: turn an empty/whitespace-only string into
    ``None`` for any application column that cannot accept a string (numeric,
    boolean, date). Text/string/JSON columns keep their value. (FPRM-464)"""
    for key, value in list(payload.items()):
        if (
            key in _NON_STRING_APPLICATION_COLUMNS
            and isinstance(value, str)
            and value.strip() == ""
        ):
            payload[key] = None


# Roles allowed to drive the application review workflow (approve/reject/request-info).
REVIEW_ROLES = {"channel_manager", "channel_ops_admin", "system_admin"}


def _serialize(app: PartnerApplication) -> dict:
    data = {c.name: getattr(app, c.name) for c in app.__table__.columns}
    return jsonable_encoder(data)


def _serialize_doc(doc: PartnerApplicationDocument) -> dict:
    return jsonable_encoder({c.name: getattr(doc, c.name) for c in doc.__table__.columns})


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _status_value(status_obj) -> str:
    return status_obj.value if hasattr(status_obj, "value") else str(status_obj)


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


def _require_review_role(current_user: User) -> None:
    if current_user.role not in REVIEW_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: review role required",
        )


def _get_application_or_404(application_id: uuid.UUID, db: Session) -> PartnerApplication:
    app_record = db.query(PartnerApplication).filter(PartnerApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_record


@router.post("", status_code=201)
@limiter.limit(_public_app_limit)
def create_draft(request: Request, response: Response, payload: dict, db: Session = Depends(get_db)):
    """Public endpoint - creates a draft application and returns id + draft_token."""
    applicant_email = (payload.get("applicant_email") or "").strip()
    if not applicant_email:
        raise HTTPException(status_code=422, detail="applicant_email is required")

    _coerce_blank_to_none(payload)
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


# Sortable column allowlist. ``program_type`` is intentionally excluded:
# the displayed "Categories" cell is derived from the JSON requested_categories
# array, which is not portably sortable across SQLite + Postgres. Falls back
# silently to default per the apply_sort helper contract.
_APPLICATION_SORT = {
    "company_name": PartnerApplication.legal_name,
    "contact_email": PartnerApplication.applicant_email,
    "status": PartnerApplication.status,
    "submitted_at": PartnerApplication.submitted_at,
    "created_at": PartnerApplication.created_at,
}


@router.get("")
def list_applications(
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    export: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_dir: Optional[str] = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Internal endpoint - paginated list of applications, filterable by status."""
    query = db.query(PartnerApplication)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            valid = {s.value for s in ApplicationStatus}
            invalid = [s for s in statuses if s not in valid]
            if invalid:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid status value(s): {invalid}. "
                        f"Allowed: {sorted(valid)}"
                    ),
                )
            query = query.filter(PartnerApplication.status.in_(statuses))
    if export == "csv":
        try:
            order_clause = PartnerApplication.submitted_at.desc().nullslast()
        except AttributeError:
            order_clause = PartnerApplication.submitted_at.desc()
        csv_rows = query.order_by(order_clause).all()
        return csv_response(
            "applications_export",
            ["Company Name", "Contact Email", "Program Type", "Status",
             "Submitted Date", "Reviewed Date"],
            [
                [
                    getattr(a, "legal_name", None) or "",
                    getattr(a, "applicant_email", None) or "",
                    (getattr(a, "requested_categories", None) or [""])[0] if getattr(a, "requested_categories", None) else "",
                    a.status.value if hasattr(a.status, "value") else (a.status or ""),
                    a.submitted_at.date().isoformat() if getattr(a, "submitted_at", None) else "",
                    a.reviewed_at.date().isoformat() if getattr(a, "reviewed_at", None) else "",
                ]
                for a in csv_rows
            ],
        )

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed=_APPLICATION_SORT,
        default_col=PartnerApplication.created_at,
        tiebreaker=PartnerApplication.id,
    )
    total = query.count()
    items = query.offset(skip).limit(limit).all()
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
    user: Optional[User] = Depends(get_optional_bearer_user),
    db: Session = Depends(get_db),
):
    """Public with ?draft_token=... OR internal with Bearer token (read_all).

    FPRM-274 / Sprint 17 — internal callers receive an ``approval_progress``
    field summarising the multi-step approval state (``None`` when no
    workflow steps are configured for ``partner_application``).
    """
    if draft_token:
        return _serialize(_validate_draft_token(application_id, draft_token, db))

    if not user:
        raise HTTPException(status_code=401, detail="draft_token or authentication required")
    if not has_permission(user.role, "partner_application:read_all"):
        raise HTTPException(status_code=403, detail="Permission denied: partner_application:read_all required")
    app_record = _get_application_or_404(application_id, db)
    data = _serialize(app_record)
    steps, _current, completed = get_approval_step_context(
        db, WORKFLOW_PARTNER_APPLICATION, app_record.id
    )
    data["approval_progress"] = build_approval_progress(steps, completed)
    return data


@router.patch("/{application_id}")
@limiter.limit(_public_app_limit)
def update_draft(
    request: Request,
    response: Response,
    application_id: uuid.UUID,
    payload: dict,
    draft_token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Public draft update via draft_token. Allowed when status is draft or info_required."""
    app_record = _validate_draft_token(application_id, draft_token, db)
    if app_record.status not in (ApplicationStatus.draft, ApplicationStatus.info_required):
        raise HTTPException(status_code=400, detail="Application cannot be edited in current status")
    _coerce_blank_to_none(payload)
    for key, value in payload.items():
        if key in PUBLIC_WRITABLE_FIELDS:
            setattr(app_record, key, value)
    app_record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)
    return _serialize(app_record)


@router.post("/{application_id}/submit")
@limiter.limit(_public_app_limit)
def submit_application(
    request: Request,
    response: Response,
    application_id: uuid.UUID,
    draft_token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Public submit via draft_token. Validates required fields then sets status=submitted.

    Also accepted from status=info_required so the applicant can resubmit after
    addressing reviewer feedback (FPRM-91).
    """
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

    before_status = _status_value(app_record.status)
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

    try:
        notify_application_submitted(app_record)
    except Exception:  # pragma: no cover  — email failures must never fail the endpoint
        pass

    return {
        "id": str(app_record.id),
        "status": _status_value(app_record.status),
        "submitted_at": app_record.submitted_at.isoformat() if app_record.submitted_at else None,
    }


@router.post("/{application_id}/documents", status_code=201)
@limiter.limit(_public_app_limit)
def upload_document_metadata(
    request: Request,
    response: Response,
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


# ---------------------- Sprint 6 review action endpoints (FPRM-90) ----------------------


@router.post("/{application_id}/approve")
def approve_application(
    application_id: uuid.UUID,
    request: Request,
    payload: Optional[dict] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Internal: approve an application. Allowed from status=submitted or under_review.

    FPRM-274 / Sprint 17 — when ``approval_workflow_steps`` defines multiple
    steps for ``partner_application``, each step must be approved by a user
    whose role matches the step's ``required_role``. Intermediate-step
    approvals stamp an ``ApprovalStepRecord`` and return ``approval_progress``
    without changing the application status. The final step runs the
    existing approval flow (status → approved, provisioning, notifications).

    If no steps are configured, single-step legacy behaviour is preserved.
    """
    _require_review_role(current_user)
    app_record = _get_application_or_404(application_id, db)

    if app_record.status not in (ApplicationStatus.submitted, ApplicationStatus.under_review):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve application in status '{_status_value(app_record.status)}'",
        )

    notes = (payload.get("notes") if payload else None) or None

    steps, current_step, completed_count = get_approval_step_context(
        db, WORKFLOW_PARTNER_APPLICATION, app_record.id,
    )

    if steps:
        if current_step is None:
            raise HTTPException(
                status_code=422,
                detail="All approval steps are already completed",
            )
        # See deal_registrations_router for the matching break-glass rule:
        # system_admin satisfies any required_role so admins can always
        # unblock a workflow stuck on a role they don't personally hold.
        if (
            current_user.role != "system_admin"
            and current_user.role != current_step.required_role
        ):
            raise HTTPException(
                status_code=403,
                detail=f"This step requires role: {current_step.required_role}",
            )

        record_step_action(
            db,
            workflow_type=WORKFLOW_PARTNER_APPLICATION,
            object_id=app_record.id,
            step=current_step,
            actor_id=current_user.id,
            action="approved",
            notes=notes,
        )

        is_final_step = (completed_count + 1) >= len(steps)

        if not is_final_step:
            db.commit()
            db.refresh(app_record)
            log_audit_event(
                db=db,
                actor=current_user,
                action="partner_application.step_approved",
                object_type="partner_application",
                object_id=app_record.id,
                before={"status": _status_value(app_record.status)},
                after={
                    "step_order": current_step.step_order,
                    "step_name": current_step.step_name,
                    "completed_steps": completed_count + 1,
                    "total_steps": len(steps),
                },
                ip_address=_client_ip(request),
            )
            data = _serialize(app_record)
            data["approval_progress"] = build_approval_progress(steps, completed_count + 1)
            data["message"] = (
                f"Step {current_step.step_order} of {len(steps)} approved. "
                "Awaiting next step."
            )
            return data
        # Final step — fall through to the existing approval flow below.

    before_status = _status_value(app_record.status)
    app_record.status = ApplicationStatus.approved
    app_record.reviewer_id = current_user.id
    app_record.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)

    # Provisioning hook — implemented in FPRM-92 (Story 3 / Sprint 6).
    invite_token = ""
    try:
        from provisioning import provision_partner_from_application  # noqa: WPS433

        result = provision_partner_from_application(db, app_record.id, current_user.id)
        invite_token = result.get("invite_token") or ""
        db.refresh(app_record)
    except ImportError:
        pass  # Provisioning module not yet present (Story 1 ships ahead of Story 3).

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_application.approved",
        object_type="partner_application",
        object_id=app_record.id,
        before={"status": before_status},
        after={
            "status": "approved",
            "partner_org_id": str(app_record.partner_org_id) if app_record.partner_org_id else None,
        },
        ip_address=_client_ip(request),
    )

    try:
        notify_application_approved(app_record, invite_token)
    except Exception:  # pragma: no cover  — email failures must never fail the endpoint
        pass

    return {
        "id": str(app_record.id),
        "status": _status_value(app_record.status),
        "partner_org_id": str(app_record.partner_org_id) if app_record.partner_org_id else None,
    }


@router.post("/{application_id}/reject")
def reject_application(
    application_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Internal: reject an application with a required reason.

    Allowed from status=submitted, under_review, or info_required.
    Stores ``rejection_reason`` on the application and logs the audit event.
    """
    _require_review_role(current_user)

    rejection_reason = (payload.get("rejection_reason") or "").strip() if payload else ""
    if not rejection_reason:
        raise HTTPException(status_code=422, detail="rejection_reason is required")

    app_record = _get_application_or_404(application_id, db)
    allowed = (ApplicationStatus.submitted, ApplicationStatus.under_review, ApplicationStatus.info_required)
    if app_record.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject application in status '{_status_value(app_record.status)}'",
        )

    # FPRM-274 / Sprint 17 — capture a step-record snapshot at rejection time
    # so the audit trail shows which step terminated the workflow.
    steps, current_step, _completed = get_approval_step_context(
        db, WORKFLOW_PARTNER_APPLICATION, app_record.id,
    )
    if steps and current_step is not None:
        record_step_action(
            db,
            workflow_type=WORKFLOW_PARTNER_APPLICATION,
            object_id=app_record.id,
            step=current_step,
            actor_id=current_user.id,
            action="rejected",
            notes=rejection_reason,
        )

    before_status = _status_value(app_record.status)
    app_record.status = ApplicationStatus.rejected
    app_record.rejection_reason = rejection_reason
    app_record.reviewer_id = current_user.id
    app_record.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_application.rejected",
        object_type="partner_application",
        object_id=app_record.id,
        before={"status": before_status},
        after={"status": "rejected", "rejection_reason": rejection_reason},
        ip_address=_client_ip(request),
    )

    try:
        notify_application_rejected(app_record, rejection_reason)
    except Exception:  # pragma: no cover
        pass

    return {
        "id": str(app_record.id),
        "status": _status_value(app_record.status),
        "rejection_reason": app_record.rejection_reason,
    }


@router.post("/{application_id}/request-info")
def request_info(
    application_id: uuid.UUID,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Internal: request additional info from the applicant.

    Allowed from status=submitted or under_review. Stores ``info_request_message`` and
    sets status=info_required so the applicant can resume the draft via the existing
    draft_token (FPRM-91 implements the resume UI).
    """
    _require_review_role(current_user)

    message = (payload.get("message") or "").strip() if payload else ""
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    app_record = _get_application_or_404(application_id, db)
    if app_record.status not in (ApplicationStatus.submitted, ApplicationStatus.under_review):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request info on application in status '{_status_value(app_record.status)}'",
        )

    before_status = _status_value(app_record.status)
    app_record.status = ApplicationStatus.info_required
    app_record.info_request_message = message
    app_record.reviewer_id = current_user.id
    app_record.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_application.info_requested",
        object_type="partner_application",
        object_id=app_record.id,
        before={"status": before_status},
        after={"status": "info_required", "info_request_message": message},
        ip_address=_client_ip(request),
    )

    try:
        notify_info_required(app_record, message)
    except Exception:  # pragma: no cover
        pass

    return {
        "id": str(app_record.id),
        "status": _status_value(app_record.status),
        "info_request_message": app_record.info_request_message,
    }


@router.post("/{application_id}/cancel-info-request")
def cancel_info_request(
    application_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("partner_application:read_all")),
):
    """Sprint 11 / FPRM-186 — reverse an outstanding info request.

    Transitions an application from ``info_required`` back to ``under_review`` and
    clears the ``info_request_message``. Allowed roles match the other review
    endpoints (channel_manager / channel_ops_admin / system_admin via
    ``_require_review_role``).
    """
    _require_review_role(current_user)
    app_record = _get_application_or_404(application_id, db)

    if app_record.status != ApplicationStatus.info_required:
        raise HTTPException(
            status_code=400,
            detail="Application is not in info_required status",
        )

    # info_request_message is set as an in-memory attribute by request-info
    # (the PartnerApplication model does not persist it). Read with getattr
    # so applications that never had an info request still serialise.
    before = {
        "status": _status_value(app_record.status),
        "info_request_message": getattr(app_record, "info_request_message", None),
    }
    app_record.status = ApplicationStatus.under_review
    app_record.info_request_message = None
    app_record.reviewer_id = current_user.id
    app_record.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)

    log_audit_event(
        db=db,
        actor=current_user,
        action="partner_application.info_request_cancelled",
        object_type="partner_application",
        object_id=app_record.id,
        before=before,
        after={"status": _status_value(app_record.status), "info_request_message": None},
        ip_address=_client_ip(request),
    )
    return {
        "id": str(app_record.id),
        "status": _status_value(app_record.status),
        "info_request_message": None,
    }


@router.get("/{application_id}/timeline")
def application_timeline(
    application_id: uuid.UUID,
    draft_token: Optional[str] = Query(default=None),
    user: Optional[User] = Depends(get_optional_bearer_user),
    db: Session = Depends(get_db),
):
    """Return the audit-log timeline for an application.

    Authorisation mirrors GET /applications/{id}: public via ``?draft_token=...``,
    OR internal via Bearer JWT with ``partner_application:read_all``.
    """
    if draft_token:
        _validate_draft_token(application_id, draft_token, db)
    else:
        if not user:
            raise HTTPException(status_code=401, detail="draft_token or authentication required")
        if not has_permission(user.role, "partner_application:read_all"):
            raise HTTPException(
                status_code=403,
                detail="Permission denied: partner_application:read_all required",
            )
        _get_application_or_404(application_id, db)

    entries = (
        db.query(AuditLog)
        .filter(AuditLog.object_id == application_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )

    return [
        {
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "action": e.action,
            "actor_role": e.actor_role,
            "before_state": e.before_state,
            "after_state": e.after_state,
        }
        for e in entries
    ]


# ---------------------- Sprint 6 message-thread endpoints (FPRM-91) ----------------------


def _serialize_message(m: PartnerApplicationMessage) -> dict:
    return jsonable_encoder({c.name: getattr(m, c.name) for c in m.__table__.columns})


@router.get("/{application_id}/messages")
def list_messages(
    application_id: uuid.UUID,
    draft_token: Optional[str] = Query(default=None),
    user: Optional[User] = Depends(get_optional_bearer_user),
    db: Session = Depends(get_db),
):
    """Public via ``?draft_token=...`` OR internal via Bearer (partner_application:read_all)."""
    if draft_token:
        _validate_draft_token(application_id, draft_token, db)
    else:
        if not user:
            raise HTTPException(status_code=401, detail="draft_token or authentication required")
        if not has_permission(user.role, "partner_application:read_all"):
            raise HTTPException(
                status_code=403,
                detail="Permission denied: partner_application:read_all required",
            )
        _get_application_or_404(application_id, db)

    rows = (
        db.query(PartnerApplicationMessage)
        .filter(PartnerApplicationMessage.application_id == application_id)
        .order_by(PartnerApplicationMessage.created_at.asc())
        .all()
    )
    return [_serialize_message(r) for r in rows]


@router.post("/{application_id}/messages", status_code=201)
def post_message(
    application_id: uuid.UUID,
    payload: dict = Body(...),
    draft_token: Optional[str] = Query(default=None),
    user: Optional[User] = Depends(get_optional_bearer_user),
    db: Session = Depends(get_db),
):
    """Post a message to the application thread.

    Public path (``?draft_token=...``) records sender_type=applicant and uses
    ``sender_email`` from the request body (falling back to the application's
    applicant_email). Internal path (JWT) records sender_type=internal,
    sender_id=current_user.id, sender_email=current_user.email.
    """
    message_text = (payload.get("message") or "").strip() if payload else ""
    if not message_text:
        raise HTTPException(status_code=422, detail="message is required")

    sender_type = None
    sender_id = None
    sender_email = ""

    if draft_token:
        app_record = _validate_draft_token(application_id, draft_token, db)
        sender_type = ApplicationMessageSender.applicant
        sender_email = (payload.get("sender_email") or app_record.applicant_email or "").strip()
        if not sender_email:
            raise HTTPException(status_code=422, detail="sender_email is required")
    else:
        if not user:
            raise HTTPException(status_code=401, detail="draft_token or authentication required")
        if not has_permission(user.role, "partner_application:read_all"):
            raise HTTPException(
                status_code=403,
                detail="Permission denied: partner_application:read_all required",
            )
        _get_application_or_404(application_id, db)
        sender_type = ApplicationMessageSender.internal
        sender_id = user.id
        sender_email = user.email

    msg = PartnerApplicationMessage(
        id=uuid.uuid4(),
        application_id=application_id,
        sender_type=sender_type,
        sender_id=sender_id,
        sender_email=sender_email,
        message=message_text,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _serialize_message(msg)

