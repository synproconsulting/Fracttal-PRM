import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLog
from permissions import require_permission

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-log")
def get_audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    object_type: Optional[str] = Query(default=None),
    action_prefix: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    export: Optional[str] = Query(default=None),
    current_user=Depends(require_permission("user_management:read_all")),
    db: Session = Depends(get_db),
):
    """Paginated audit log with optional filters. Requires system_admin role.

    Sprint 19 / FPRM-308: adds ``action_prefix`` to filter by action dot-prefix
    (e.g. ``action_prefix=pricing`` matches ``pricing.plan_price_created``,
    ``pricing.addon_updated`` etc) and ``?export=csv`` to download the
    filtered set as CSV (auth via the same Bearer header thanks to AD-20).
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

    if object_type:
        query = query.filter(AuditLog.object_type == object_type)
    if action_prefix:
        query = query.filter(AuditLog.action.like(f"{action_prefix}.%"))
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if date_from:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to:
        query = query.filter(AuditLog.timestamp <= date_to)

    if (export or "").lower() == "csv":
        # Reasonable upper bound for an interactive export; matches AD-20 /
        # other CSV exports in this codebase.
        rows = query.limit(5000).all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Timestamp", "Actor Role", "Actor ID", "Action", "Object Type", "Object ID", "Notes"])
        for r in rows:
            writer.writerow([
                r.timestamp.isoformat() if r.timestamp else "",
                r.actor_role or "",
                str(r.actor_id) if r.actor_id else "",
                r.action or "",
                r.object_type or "",
                str(r.object_id) if r.object_id else "",
                r.notes or "",
            ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(item.id),
                "timestamp": item.timestamp.isoformat(),
                "actor_id": str(item.actor_id) if item.actor_id is not None else None,
                "actor_role": item.actor_role,
                "action": item.action,
                "object_type": item.object_type,
                "object_id": str(item.object_id) if item.object_id else None,
                "before_state": item.before_state,
                "after_state": item.after_state,
                "ip_address": item.ip_address,
                "notes": item.notes,
            }
            for item in items
        ],
    }
