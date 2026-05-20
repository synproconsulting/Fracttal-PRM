"""Sprint 16 / FPRM-262 - CSV export smoke tests across the 7 list endpoints."""
import os
import sys
import uuid
from datetime import date, datetime
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
    DealRegistration,
    PartnerCategory,
    PartnerOrganization,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///./test_csv_export.db",
                        connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists("./test_csv_export.db"):
        try:
            os.remove("./test_csv_export.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        s.rollback()
        for tbl in (
            "partner_user_invites", "deal_registrations",
            "users", "partner_organizations", "audit_log",
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
        legal_name=f"Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
    )
    db.add(o)
    db.commit()
    return o


def make_deal(db, org_id, status="submitted"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", customer_domain="example.com",
        deal_name="D", estimated_deal_value=10000.0,
        submitted_at=datetime.utcnow(),
        commission_type="distributor", commission_rate_snapshot=15.0,
    )
    db.add(d)
    db.commit()
    return d


def auth(client, user):
    app.dependency_overrides[get_current_user] = lambda: user


def _is_csv(resp, expected_header):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv"), resp.headers
    cd = resp.headers.get("content-disposition") or resp.headers.get("Content-Disposition")
    assert cd and "attachment" in cd.lower(), cd
    lines = resp.text.strip().split("\n")
    assert lines[0].strip() == expected_header.strip(), f"Header mismatch: {lines[0]!r}"


# ============================================================
# Tests - one per endpoint
# ============================================================


def test_portal_deals_csv_export(client, db_session):
    org = make_org(db_session)
    make_deal(db_session, org.id)
    user = make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    auth(client, user)
    r = client.get("/deal-registrations?export=csv")
    _is_csv(r, "Deal Name,Customer Domain,Partner Org,Deal Value,Status,Submitted Date,Commission Type,Commission Rate")


def test_internal_deals_csv_export(client, db_session):
    org = make_org(db_session)
    make_deal(db_session, org.id)
    user = make_user(db_session, UserRole.channel_manager.value)
    auth(client, user)
    r = client.get("/internal/deals?export=csv")
    _is_csv(r, "Deal Name,Customer Domain,Partner Org,Deal Value,Status,Submitted Date,Commission Type,Commission Rate")


def test_partner_documents_csv_export(client, db_session):
    org = make_org(db_session)
    user = make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    auth(client, user)
    r = client.get(f"/partners/{org.id}/documents?export=csv")
    _is_csv(r, "Partner Org,Document Type,Status,Uploaded Date,Reviewed Date,Reviewer")


def test_internal_partners_csv_export(client, db_session):
    make_org(db_session)
    user = make_user(db_session, UserRole.channel_manager.value)
    auth(client, user)
    r = client.get("/internal/partners?export=csv")
    _is_csv(r, "Legal Name,Program Type,Category,Tier,Status,Activation Complete,Created Date")


def test_internal_partner_users_csv_export(client, db_session):
    org = make_org(db_session)
    make_user(db_session, UserRole.partner_admin.value, org_id=org.id)
    admin = make_user(db_session, UserRole.system_admin.value)
    auth(client, admin)
    r = client.get("/internal/partner-users?export=csv")
    _is_csv(r, "Email,Full Name,Role,Partner Org,Status,Created Date")


def test_applications_csv_export(client, db_session):
    admin = make_user(db_session, UserRole.channel_manager.value)
    auth(client, admin)
    r = client.get("/applications?export=csv")
    _is_csv(r, "Company Name,Contact Email,Program Type,Status,Submitted Date,Reviewed Date")


def test_internal_users_csv_export(client, db_session):
    admin = make_user(db_session, UserRole.system_admin.value)
    auth(client, admin)
    r = client.get("/internal/users?export=csv")
    _is_csv(r, "Email,Full Name,Role,Is Active,Last Login,Created Date")
