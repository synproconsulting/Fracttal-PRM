"""Tests for Sprint 16 / FPRM-258 - PDF quote generation."""
import base64
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    AddonCatalogItem,
    DealRegistration,
    FeaturePlanPrice,
    PartnerCategory,
    PartnerOrganization,
    ProgramType,
    Quote,
    QuoteVersion,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///./test_quote_pdf.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_quote_pdf.db"):
        try:
            os.remove("./test_quote_pdf.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "quote_line_items", "quote_versions", "quotes",
            "addon_catalog_items", "volume_discount_tiers", "feature_plan_prices",
            "deal_registrations", "users", "partner_organizations", "audit_log",
        ):
            try:
                s.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        s.commit()
        s.close()


@pytest.fixture()
def client(db_session):
    def _override_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def seed_pricing(db):
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter",      feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise",   feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1,   max_users=10,   transactional_user_discount_pct=Decimal("0"),  limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11,  max_users=50,   transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51,  max_users=100,  transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300,  transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500,  transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    db.add(AddonCatalogItem(
        addon_key="fracttal_hub", display_name="FRACTTAL_HUB",
        monthly_price=Decimal("55.00"),
        available_starter=True, available_professional=True,
        included_enterprise=True, is_active=True,
    ))
    db.commit()


def make_user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u)
    db.commit()
    return u


def make_org(db):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Test Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o)
    db.commit()
    return o


def make_deal(db, org_id, status="approved"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="Customer A", deal_name="Deal A",
    )
    db.add(d)
    db.commit()
    return d


def auth(client, user):
    app.dependency_overrides[get_current_user] = lambda: user


def create_quote(client, deal):
    r = client.post(f"/deals/{deal.id}/quotes", json={
        "feature_plan": "enterprise",
        "feature_plan_discount_pct": 0,
        "qty_transactional_users": 5,
        "qty_limited_tech_users": 5,
        "selected_addon_keys": [],
    })
    assert r.status_code == 201, r.text
    return r.json()


# ============================================================
# Tests
# ============================================================


def test_generate_pdf_returns_200(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    r = client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pdf_filename" in body
    assert body["pdf_filename"].endswith(".pdf")
    assert "pdf_generated_at" in body


def test_generate_pdf_sets_db_fields(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    qv = (
        db_session.query(QuoteVersion)
        .filter(QuoteVersion.quote_id == uuid.UUID(q["id"]),
                QuoteVersion.version_number == 1)
        .first()
    )
    assert qv.pdf_artifact_data is not None
    assert qv.pdf_generated_at is not None
    assert qv.pdf_filename is not None
    assert qv.pdf_filename.endswith(".pdf")


def test_generate_pdf_idempotent(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    r1 = client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    r2 = client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["pdf_filename"] == r2.json()["pdf_filename"]


def test_download_pdf_returns_application_pdf(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    r = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_download_pdf_content_disposition_header(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    r = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert "Content-Disposition" in r.headers or "content-disposition" in r.headers
    cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition")
    assert "attachment" in cd.lower()
    assert ".pdf" in cd


def test_download_before_generate_returns_404(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    r = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert r.status_code == 404


def test_partner_admin_can_download_own_pdf(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    cm = make_user(db_session, UserRole.channel_manager.value)
    auth(client, cm)
    q = create_quote(client, deal)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    # switch to partner_admin of same org
    pa = make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    auth(client, pa)
    r = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert r.status_code == 200, r.text


def test_partner_admin_cannot_download_other_org_pdf(client, db_session):
    org_a = make_org(db_session)
    org_b = make_org(db_session)
    deal_a = make_deal(db_session, org_a.id)
    cm = make_user(db_session, UserRole.channel_manager.value)
    auth(client, cm)
    q = create_quote(client, deal_a)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    # partner_admin of org_b should not be able to download org_a's quote
    other = make_user(db_session, UserRole.partner_admin.value, org_id=org_b.id)
    auth(client, other)
    r = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert r.status_code == 403


def test_internal_role_can_generate_and_download(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    admin = make_user(db_session, UserRole.system_admin.value)
    auth(client, admin)
    q = create_quote(client, deal)
    g = client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    d = client.get(f"/quotes/{q['id']}/versions/1/pdf")
    assert g.status_code == 200
    assert d.status_code == 200


def test_pdf_bytes_valid_pdf_header(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    auth(client, make_user(db_session, UserRole.channel_manager.value))
    q = create_quote(client, deal)
    client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    qv = (
        db_session.query(QuoteVersion)
        .filter(QuoteVersion.quote_id == uuid.UUID(q["id"]),
                QuoteVersion.version_number == 1)
        .first()
    )
    pdf_bytes = base64.b64decode(qv.pdf_artifact_data)
    assert pdf_bytes.startswith(b"%PDF"), "Decoded artefact must start with PDF header"


def test_partner_admin_cannot_generate_pdf(client, db_session):
    org = make_org(db_session)
    deal = make_deal(db_session, org.id)
    cm = make_user(db_session, UserRole.channel_manager.value)
    auth(client, cm)
    q = create_quote(client, deal)
    pa = make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    auth(client, pa)
    r = client.post(f"/quotes/{q['id']}/versions/1/generate-pdf")
    assert r.status_code == 403
