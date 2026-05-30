"""Asset Library (Sprint 23 PR B / FR-PORT-020..023 / AD-39).

Marketing / enablement asset catalogue. Binary content is stored
base64-encoded in ``assets.file_data`` (AD-17/AD-19). ``file_data`` is NEVER
returned by any list endpoint -- only ``GET /assets/{id}/download`` streams
the decoded bytes (AD-20).

Permissions
-----------
GET    /assets                              any authenticated user (partner portal; visibility-filtered)
GET    /assets/{id}/download                any authenticated user (visibility-checked); +count; +log
GET    /internal/assets                     asset:read_all (channel_manager+)
POST   /internal/assets                     asset:create (channel_ops_admin / system_admin); 10 MB cap
PATCH  /internal/assets/{id}                asset:update_all (channel_ops_admin+)
DELETE /internal/assets/{id}                system_admin only; soft delete (is_active=false)
GET    /internal/asset-categories           any internal role
POST   /internal/asset-categories           asset:create
PATCH  /internal/asset-categories/{id}      asset:update_all
DELETE /internal/asset-categories/{id}      system_admin only; soft delete

Visibility: ``all`` | ``tier:<tier>`` | ``category:<code>`` -- enforced on
``GET /assets`` and the download endpoint against the caller's partner org.
"""
import base64
import binascii
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from auth import get_current_user
from audit import log_audit_event
from database import get_db
from models import Asset, AssetCategory, AssetDownloadLog, PartnerOrganization, User
from permissions import require_permission
from roles import INTERNAL_ROLES, PARTNER_ROLES, UserRole

router = APIRouter(tags=["assets"])

MAX_ASSET_BYTES = 10 * 1024 * 1024  # 10 MB cap (AD-39 -- independent of the 25 MB partner-documents cap)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def _enum_value(v) -> Optional[str]:
    if v is None:
        return None
    return str(getattr(v, "value", v))


def _serialize_asset(a: Asset, *, include_category_name: bool = True) -> dict:
    """Asset metadata WITHOUT file_data (AD-39 -- bytes only via download)."""
    return {
        "id": str(a.id),
        "category_id": str(a.category_id) if a.category_id else None,
        "category_name": (a.category.name if (include_category_name and a.category) else None),
        "title": a.title,
        "description": a.description,
        "file_name": a.file_name,
        "file_type": a.file_type,
        "file_size_bytes": a.file_size_bytes,
        "visibility": a.visibility,
        "is_active": bool(a.is_active),
        "download_count": a.download_count or 0,
        "uploaded_by": str(a.uploaded_by) if a.uploaded_by else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _serialize_category(c: AssetCategory) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "display_order": c.display_order,
        "is_active": bool(c.is_active),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _caller_org(db: Session, user: User) -> Optional[PartnerOrganization]:
    if user.partner_org_id is None:
        return None
    return (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == user.partner_org_id)
        .first()
    )


def _visible_to(asset: Asset, user: User, org: Optional[PartnerOrganization]) -> bool:
    """Visibility check for the partner portal.

    Internal roles bypass visibility (they manage the catalogue). Partner
    roles see ``all`` plus assets matching their org's tier / category.
    """
    if UserRole(user.role) in INTERNAL_ROLES:
        return True
    v = (asset.visibility or "all").strip()
    if v == "all":
        return True
    if v.lower().startswith("tier:"):
        want = v.split(":", 1)[1].strip().lower()
        return org is not None and (_enum_value(org.tier) or "").lower() == want
    if v.lower().startswith("category:"):
        want = v.split(":", 1)[1].strip().lower()
        return org is not None and (_enum_value(org.partner_category) or "").lower() == want
    return False


# ============================ Partner portal ============================


@router.get("/assets")
def list_assets(
    category_id: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partner portal list -- active + visibility-eligible only. Never
    returns ``file_data``."""
    org = _caller_org(db, current_user)
    query = db.query(Asset).filter(Asset.is_active.is_(True))
    if category_id is not None:
        query = query.filter(Asset.category_id == category_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(Asset.title.ilike(like))
    query = query.order_by(Asset.created_at.desc())
    eligible = [a for a in query.all() if _visible_to(a, current_user, org)]
    total = len(eligible)
    start = (page - 1) * page_size
    rows = eligible[start:start + page_size]
    return {
        "items": [_serialize_asset(a) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/assets/{asset_id}/download")
def download_asset(
    asset_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the asset binary (AD-20). Visibility-checked; increments
    ``download_count`` and writes an ``asset_download_logs`` row."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None or not asset.is_active:
        raise HTTPException(status_code=404, detail="Asset not found")
    org = _caller_org(db, current_user)
    if not _visible_to(asset, current_user, org):
        # 404 (not 403) so a guessed id can't reveal a restricted asset's existence.
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        body = base64.b64decode(asset.file_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=500, detail="Stored asset is corrupt")

    asset.download_count = (asset.download_count or 0) + 1
    db.add(AssetDownloadLog(
        id=uuid.uuid4(),
        asset_id=asset.id,
        downloaded_by=current_user.id,
        partner_org_id=current_user.partner_org_id,
    ))
    db.commit()

    log_audit_event(
        db=db, actor=current_user, action="asset.downloaded",
        object_type="asset", object_id=asset.id,
        after={"download_count": asset.download_count},
        ip_address=_client_ip(request),
    )

    safe_name = (asset.file_name or "asset").replace('"', "")
    mime = asset.file_type or "application/octet-stream"
    return Response(
        content=body, media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(body)),
        },
    )


# ============================ Internal management ============================


@router.get("/internal/assets")
def internal_list_assets(
    category_id: Optional[uuid.UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:read_all")),
):
    """Internal list -- includes inactive + download_count. No file_data."""
    query = db.query(Asset)
    if category_id is not None:
        query = query.filter(Asset.category_id == category_id)
    if is_active is not None:
        query = query.filter(Asset.is_active.is_(is_active))
    if search:
        query = query.filter(Asset.title.ilike(f"%{search.strip()}%"))
    rows = query.order_by(Asset.created_at.desc()).all()
    return {"items": [_serialize_asset(a) for a in rows]}


@router.post("/internal/assets", status_code=201)
def create_asset(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:create")),
):
    """Upload an asset. Body: title, file_name, file_data (base64),
    optional description / category_id / visibility / file_type /
    file_size_bytes / thumbnail_data. 10 MB cap."""
    for required in ("title", "file_name", "file_data"):
        if not payload.get(required):
            raise HTTPException(status_code=422, detail=f"{required} is required")

    file_data = payload["file_data"]
    if not isinstance(file_data, str):
        raise HTTPException(status_code=422, detail="file_data must be a base64 string")
    try:
        decoded = base64.b64decode(file_data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="file_data is not valid base64")
    if len(decoded) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=422, detail="File too large. Maximum asset size is 10 MB.")

    declared = payload.get("file_size_bytes")
    if declared is not None:
        if not isinstance(declared, int) or declared < 0:
            raise HTTPException(status_code=422, detail="file_size_bytes must be a non-negative integer")
        if declared > MAX_ASSET_BYTES:
            raise HTTPException(status_code=422, detail="File too large. Maximum asset size is 10 MB.")

    category_id = payload.get("category_id")
    if category_id:
        try:
            category_id = uuid.UUID(str(category_id))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="category_id must be a UUID")
        if db.query(AssetCategory).filter(AssetCategory.id == category_id).first() is None:
            raise HTTPException(status_code=422, detail="category_id does not exist")

    asset = Asset(
        id=uuid.uuid4(),
        category_id=category_id or None,
        title=payload["title"],
        description=payload.get("description"),
        file_name=payload["file_name"],
        file_type=payload.get("file_type"),
        file_size_bytes=declared if declared is not None else len(decoded),
        file_data=file_data,
        thumbnail_data=payload.get("thumbnail_data"),
        visibility=(payload.get("visibility") or "all").strip(),
        is_active=True,
        uploaded_by=current_user.id,
        download_count=0,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    log_audit_event(
        db=db, actor=current_user, action="asset.uploaded",
        object_type="asset", object_id=asset.id,
        after=_serialize_asset(asset), ip_address=_client_ip(request),
    )
    return _serialize_asset(asset)


@router.patch("/internal/assets/{asset_id}")
def update_asset(
    asset_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:update_all")),
):
    """Update metadata (title/description/category/visibility/is_active).
    ``file_data`` is immutable here -- re-upload to replace bytes."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    before = _serialize_asset(asset)

    if "title" in payload and payload["title"]:
        asset.title = payload["title"]
    if "description" in payload:
        asset.description = payload["description"]
    if "visibility" in payload and payload["visibility"]:
        asset.visibility = str(payload["visibility"]).strip()
    if "is_active" in payload:
        asset.is_active = bool(payload["is_active"])
    if "category_id" in payload:
        cid = payload["category_id"]
        if cid:
            try:
                cid = uuid.UUID(str(cid))
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="category_id must be a UUID")
            if db.query(AssetCategory).filter(AssetCategory.id == cid).first() is None:
                raise HTTPException(status_code=422, detail="category_id does not exist")
            asset.category_id = cid
        else:
            asset.category_id = None

    db.commit()
    db.refresh(asset)
    log_audit_event(
        db=db, actor=current_user, action="asset.updated",
        object_type="asset", object_id=asset.id,
        before=before, after=_serialize_asset(asset), ip_address=_client_ip(request),
    )
    return _serialize_asset(asset)


@router.delete("/internal/assets/{asset_id}")
def delete_asset(
    asset_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete (is_active=false). system_admin only."""
    if UserRole(current_user.role) != UserRole.system_admin:
        raise HTTPException(status_code=403, detail="Only system_admin can delete assets")
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.is_active = False
    db.commit()
    log_audit_event(
        db=db, actor=current_user, action="asset.deactivated",
        object_type="asset", object_id=asset.id, ip_address=_client_ip(request),
    )
    return {"deactivated": True, "id": str(asset_id)}


@router.get("/internal/assets/{asset_id}/download-logs")
def asset_download_logs(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:read_all")),
):
    """Download-log detail for the internal download-count drill-down."""
    if db.query(Asset).filter(Asset.id == asset_id).first() is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    rows = (
        db.query(AssetDownloadLog)
        .filter(AssetDownloadLog.asset_id == asset_id)
        .order_by(AssetDownloadLog.downloaded_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "downloaded_by": str(r.downloaded_by) if r.downloaded_by else None,
                "partner_org_id": str(r.partner_org_id) if r.partner_org_id else None,
                "downloaded_at": r.downloaded_at.isoformat() if r.downloaded_at else None,
            }
            for r in rows
        ]
    }


# ============================ Categories ============================


@router.get("/internal/asset-categories")
def list_asset_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if UserRole(current_user.role) not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail="Internal role required")
    rows = (
        db.query(AssetCategory)
        .order_by(AssetCategory.display_order.asc(), AssetCategory.name.asc())
        .all()
    )
    return {"items": [_serialize_category(c) for c in rows]}


@router.post("/internal/asset-categories", status_code=201)
def create_asset_category(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:create")),
):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if db.query(AssetCategory).filter(AssetCategory.name == name).first() is not None:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    cat = AssetCategory(
        id=uuid.uuid4(),
        name=name,
        description=payload.get("description"),
        display_order=int(payload.get("display_order", 0)),
        is_active=True,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    log_audit_event(
        db=db, actor=current_user, action="asset_category.created",
        object_type="asset_category", object_id=cat.id,
        after=_serialize_category(cat), ip_address=_client_ip(request),
    )
    return _serialize_category(cat)


@router.patch("/internal/asset-categories/{category_id}")
def update_asset_category(
    category_id: uuid.UUID,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("asset:update_all")),
):
    cat = db.query(AssetCategory).filter(AssetCategory.id == category_id).first()
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    before = _serialize_category(cat)
    if "name" in payload and payload["name"]:
        cat.name = str(payload["name"]).strip()
    if "description" in payload:
        cat.description = payload["description"]
    if "display_order" in payload:
        cat.display_order = int(payload["display_order"])
    if "is_active" in payload:
        cat.is_active = bool(payload["is_active"])
    db.commit()
    db.refresh(cat)
    log_audit_event(
        db=db, actor=current_user, action="asset_category.updated",
        object_type="asset_category", object_id=cat.id,
        before=before, after=_serialize_category(cat), ip_address=_client_ip(request),
    )
    return _serialize_category(cat)


@router.delete("/internal/asset-categories/{category_id}")
def delete_asset_category(
    category_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete (is_active=false). system_admin only."""
    if UserRole(current_user.role) != UserRole.system_admin:
        raise HTTPException(status_code=403, detail="Only system_admin can delete categories")
    cat = db.query(AssetCategory).filter(AssetCategory.id == category_id).first()
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    db.commit()
    log_audit_event(
        db=db, actor=current_user, action="asset_category.deactivated",
        object_type="asset_category", object_id=cat.id, ip_address=_client_ip(request),
    )
    return {"deactivated": True, "id": str(category_id)}
