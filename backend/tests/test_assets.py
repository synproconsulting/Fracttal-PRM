"""Sprint 23 PR B / AD-39 -- Asset Library API tests."""
import base64
import importlib.util
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    Asset,
    AssetCategory,
    AssetDownloadLog,
    PartnerCategory,
    PartnerOrganization,
    PartnerTier,
    User,
)
from roles import UserRole


_BYTES = b"hello asset bytes"
_B64 = base64.b64encode(_BYTES).decode()


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        from sqlalchemy import text
        s.rollback()
        for tbl in ("asset_download_logs", "assets", "asset_categories", "audit_log",
                    "users", "partner_organizations"):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db):
    def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _user(db, role, partner_org_id=None):
    u = User(id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@t",
             hashed_password="x", role=role, is_active=True, partner_org_id=partner_org_id)
    db.add(u); db.commit()
    return u


def _org(db, tier=PartnerTier.gold, category=PartnerCategory.reseller):
    p = PartnerOrganization(id=uuid.uuid4(), legal_name=f"Org {uuid.uuid4().hex[:4]}",
                            program_type="distributor", partner_category=category,
                            status="active", tier=tier)
    db.add(p); db.commit()
    return p


def _category(client, db, name="Brochures"):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    r = client.post("/internal/asset-categories", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(client, db, **over):
    body = {"title": "Datasheet", "file_name": "d.pdf", "file_data": _B64,
            "file_type": "application/pdf", "file_size_bytes": len(_BYTES),
            "visibility": "all"}
    body.update(over)
    return client.post("/internal/assets", json=body)


# ----- migration importability -----

def test_migration_040_importable():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full = os.path.join(here, "alembic", "versions", "040_create_asset_library.py")
    spec = importlib.util.spec_from_file_location("mig040", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "040" and mod.down_revision == "039"
    assert hasattr(mod, "upgrade") and hasattr(mod, "downgrade")


# ----- upload / list -----

def test_upload_stores_base64_and_list_excludes_file_data(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    r = _upload(client, db)
    assert r.status_code == 201, r.text
    asset_id = r.json()["id"]
    assert "file_data" not in r.json()
    row = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    assert row.file_data == _B64
    # Internal list excludes file_data
    items = client.get("/internal/assets").json()["items"]
    assert len(items) == 1 and "file_data" not in items[0]


def test_upload_over_10mb_returns_422(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    r = _upload(client, db, file_size_bytes=11 * 1024 * 1024)
    assert r.status_code == 422
    assert "10 MB" in r.json()["detail"]


def test_partner_cannot_upload(client, db):
    org = _org(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=org.id))
    r = _upload(client, db)
    assert r.status_code == 403


def test_partner_cannot_patch_or_delete(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db).json()["id"]
    org = _org(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=org.id))
    assert client.patch(f"/internal/assets/{asset_id}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/internal/assets/{asset_id}").status_code == 403


# ----- download + count + log -----

def test_download_returns_bytes_increments_count_and_logs(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db).json()["id"]
    org = _org(db)
    pu = _user(db, UserRole.partner_user.value, partner_org_id=org.id)
    _auth(pu)
    r = client.get(f"/assets/{asset_id}/download")
    assert r.status_code == 200
    assert r.content == _BYTES
    row = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    assert row.download_count == 1
    logs = db.query(AssetDownloadLog).filter(AssetDownloadLog.asset_id == uuid.UUID(asset_id)).all()
    assert len(logs) == 1 and logs[0].partner_org_id == org.id


# ----- visibility -----

def test_visibility_all_visible_to_partner(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    _upload(client, db, visibility="all", title="Public")
    org = _org(db, tier=PartnerTier.silver)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=org.id))
    items = client.get("/assets").json()["items"]
    assert any(a["title"] == "Public" for a in items)


def test_visibility_tier_gold_filters(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    _upload(client, db, visibility="tier:gold", title="GoldOnly")
    # Silver partner does NOT see it
    silver = _org(db, tier=PartnerTier.silver)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=silver.id))
    assert not any(a["title"] == "GoldOnly" for a in client.get("/assets").json()["items"])
    # Gold partner DOES see it
    gold = _org(db, tier=PartnerTier.gold)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=gold.id))
    assert any(a["title"] == "GoldOnly" for a in client.get("/assets").json()["items"])


def test_download_visibility_denied_returns_404(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db, visibility="tier:gold").json()["id"]
    silver = _org(db, tier=PartnerTier.silver)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=silver.id))
    assert client.get(f"/assets/{asset_id}/download").status_code == 404


# ----- internal list inactive + soft delete -----

def test_internal_list_includes_inactive_and_soft_delete(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db).json()["id"]
    # system_admin soft-deletes
    _auth(_user(db, UserRole.system_admin.value))
    assert client.delete(f"/internal/assets/{asset_id}").status_code == 200
    row = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    assert row.is_active is False
    # internal list (no filter) still includes it
    _auth(_user(db, UserRole.channel_manager.value))
    items = client.get("/internal/assets").json()["items"]
    assert any(a["id"] == asset_id for a in items)
    # partner portal list excludes inactive
    org = _org(db)
    _auth(_user(db, UserRole.partner_admin.value, partner_org_id=org.id))
    assert not any(a["id"] == asset_id for a in client.get("/assets").json()["items"])


def test_channel_ops_delete_forbidden_system_admin_only(client, db):
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db).json()["id"]
    # channel_ops_admin (has asset:delete perm) is still blocked -- DELETE is system_admin-only
    assert client.delete(f"/internal/assets/{asset_id}").status_code == 403


# ----- categories -----

def test_category_create_list_and_soft_delete(client, db):
    cid = _category(client, db, name="Logos")
    _auth(_user(db, UserRole.channel_manager.value))
    cats = client.get("/internal/asset-categories").json()["items"]
    assert any(c["id"] == cid for c in cats)
    # duplicate name 409
    _auth(_user(db, UserRole.channel_ops_admin.value))
    assert client.post("/internal/asset-categories", json={"name": "Logos"}).status_code == 409
    # soft delete (system_admin)
    _auth(_user(db, UserRole.system_admin.value))
    assert client.delete(f"/internal/asset-categories/{cid}").status_code == 200
    assert db.query(AssetCategory).filter(AssetCategory.id == uuid.UUID(cid)).first().is_active is False


def test_upload_with_category_and_download_logs_endpoint(client, db):
    cid = _category(client, db, name="Decks")
    _auth(_user(db, UserRole.channel_ops_admin.value))
    asset_id = _upload(client, db, category_id=cid).json()["id"]
    # drive a download then read the logs endpoint
    org = _org(db)
    _auth(_user(db, UserRole.partner_user.value, partner_org_id=org.id))
    client.get(f"/assets/{asset_id}/download")
    _auth(_user(db, UserRole.channel_manager.value))
    logs = client.get(f"/internal/assets/{asset_id}/download-logs").json()["items"]
    assert len(logs) == 1
