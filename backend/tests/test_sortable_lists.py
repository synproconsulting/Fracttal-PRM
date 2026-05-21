"""Tests for the sortable column wiring added to every list endpoint.

The shared ``apply_sort`` helper in ``backend/sorting.py`` runs every
endpoint's ``?sort_by=…&sort_dir=asc|desc`` input through a per-endpoint
column allowlist. These tests exercise the contract:

* Deep ordering correctness on a representative endpoint (``/internal/deals``)
  for asc + desc + invalid fallback paths.
* Smoke checks across every other sortable list endpoint to confirm the
  query params are accepted and the response shape is unchanged.

Coverage on the simpler endpoints is deliberately shallow -- the ordering
itself is the helper's job and is exercised end-to-end on /internal/deals;
the per-endpoint smoke tests just confirm the wiring is correct and a
hostile ``sort_by`` value can't crash the handler.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user
from database import Base, get_db
import models  # noqa: F401
from models import (
    DealRegistration,
    PartnerActivationChecklist,
    PartnerApplication,
    ApplicationStatus,
    PartnerCategory,
    PartnerDocument,
    PartnerOrganization,
    PartnerStatus,
    PartnerTier,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture()
def db_session(tmp_path):
    """Fresh file-backed SQLite per test so sort assertions can be made
    against an exactly-known dataset without cross-test contamination.

    A literal ``:memory:`` SQLite gives each connection its own private
    database, which breaks the FastAPI dependency-override pattern (the
    test session's schema isn't visible to the request handler's session).
    """
    db_path = tmp_path / "sortable_lists.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _override_user(db_session, user):
    def _override_db():
        yield db_session

    def _override_user_fn():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user_fn


def _clear_overrides():
    app.dependency_overrides.clear()


def _make_user(role: UserRole, partner_org_id=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role=role.value,
        partner_org_id=partner_org_id,
        is_active=True,
    )


def _make_org(db, *, name: str = None) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=name or f"Sort Org {uuid.uuid4().hex[:6]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=PartnerStatus.active,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_deals(db, org_id):
    """Three deals with distinct deal_name + estimated_deal_value + created_at."""
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    deals = []
    for i, (name, value) in enumerate([
        ("Bravo Deal", 200.0),
        ("Alpha Deal", 100.0),
        ("Charlie Deal", 300.0),
    ]):
        d = DealRegistration(
            id=uuid.uuid4(),
            partner_org_id=org_id,
            status="draft",
            customer_name=f"Customer {i}",
            deal_name=name,
            estimated_deal_value=value,
            created_at=base_time + timedelta(days=i),
            updated_at=base_time + timedelta(days=i),
        )
        db.add(d)
        deals.append(d)
    db.commit()
    return deals


# ------------------ Deep test on /internal/deals ------------------


def test_internal_deals_sort_by_deal_name_asc(db_session):
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?sort_by=deal_name&sort_dir=asc")
        assert r.status_code == 200, r.text
        names = [d["deal_name"] for d in r.json()["items"]]
        assert names == ["Alpha Deal", "Bravo Deal", "Charlie Deal"]
    finally:
        _clear_overrides()


def test_internal_deals_sort_by_deal_name_desc(db_session):
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?sort_by=deal_name&sort_dir=desc")
        assert r.status_code == 200
        names = [d["deal_name"] for d in r.json()["items"]]
        assert names == ["Charlie Deal", "Bravo Deal", "Alpha Deal"]
    finally:
        _clear_overrides()


def test_internal_deals_sort_by_deal_value_asc(db_session):
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?sort_by=deal_value&sort_dir=asc")
        assert r.status_code == 200
        values = [d["estimated_deal_value"] for d in r.json()["items"]]
        assert values == [100.0, 200.0, 300.0]
    finally:
        _clear_overrides()


def test_internal_deals_sort_by_partner_org_asc(db_session):
    org_z = _make_org(db_session, name="Zeta Org")
    org_a = _make_org(db_session, name="Alpha Org")
    _seed_deals(db_session, org_z.id)
    _seed_deals(db_session, org_a.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?sort_by=partner_org&sort_dir=asc")
        assert r.status_code == 200
        legal_names = [d["partner_legal_name"] for d in r.json()["items"]]
        # All "Alpha Org" deals come before all "Zeta Org" deals
        assert legal_names[:3] == ["Alpha Org"] * 3
        assert legal_names[3:] == ["Zeta Org"] * 3
    finally:
        _clear_overrides()


def test_internal_deals_invalid_sort_by_falls_back_to_default(db_session):
    """Unknown sort_by values must NOT 422 -- they fall back silently to
    the endpoint's default (created_at desc). Hostile column names like
    ``DROP TABLE`` can't reach the SQL layer because the allowlist rejects
    them before column lookup."""
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        for bogus in ("nope", "1; DROP TABLE deal_registrations; --", "id"):
            r = client.get(f"/internal/deals?sort_by={bogus}&sort_dir=asc")
            assert r.status_code == 200, f"{bogus}: {r.text}"
            # Bogus sort_by silently falls back to created_at desc (the
            # endpoint default). _seed_deals adds (Bravo, Alpha, Charlie)
            # with monotonically increasing created_at, so newest first =
            # Charlie, Alpha, Bravo. The fact that this matches the
            # default-sort test proves the bogus key didn't crash and
            # didn't leak through as a column reference.
            names = [d["deal_name"] for d in r.json()["items"]]
            assert names == ["Charlie Deal", "Alpha Deal", "Bravo Deal"]
    finally:
        _clear_overrides()


def test_internal_deals_invalid_sort_dir_falls_back(db_session):
    """A known sort_by with garbage sort_dir falls back to default direction."""
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals?sort_by=deal_name&sort_dir=sideways")
        assert r.status_code == 200
        # default direction is desc, so newest first by name
        names = [d["deal_name"] for d in r.json()["items"]]
        assert names == ["Charlie Deal", "Bravo Deal", "Alpha Deal"]
    finally:
        _clear_overrides()


def test_internal_deals_default_order_is_created_at_desc(db_session):
    """No sort_by query param -> default (created_at desc)."""
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/deals")
        assert r.status_code == 200
        names = [d["deal_name"] for d in r.json()["items"]]
        # _seed_deals adds in (Bravo, Alpha, Charlie) order with monotonically
        # increasing created_at, so newest first = Charlie, Alpha, Bravo.
        assert names == ["Charlie Deal", "Alpha Deal", "Bravo Deal"]
    finally:
        _clear_overrides()


# ------------------ Portal /deal-registrations smoke ------------------


def test_portal_deals_sort_by_deal_name_asc(db_session):
    org = _make_org(db_session)
    _seed_deals(db_session, org.id)
    user = _make_user(UserRole.partner_admin, partner_org_id=org.id)
    _override_user(db_session, user)
    client = TestClient(app)
    try:
        r = client.get("/deal-registrations?sort_by=deal_name&sort_dir=asc")
        assert r.status_code == 200
        names = [d["deal_name"] for d in r.json()["items"]]
        assert names == ["Alpha Deal", "Bravo Deal", "Charlie Deal"]

        # Invalid sort_by silently falls back -- no 422
        r = client.get("/deal-registrations?sort_by=evil&sort_dir=asc")
        assert r.status_code == 200
    finally:
        _clear_overrides()


# ------------------ /applications smoke ------------------


def _seed_applications(db):
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    apps = []
    for i, name in enumerate(["Bravo Co", "Alpha Co", "Charlie Co"]):
        a = PartnerApplication(
            id=uuid.uuid4(),
            status=ApplicationStatus.submitted,
            applicant_email=f"user{i}@{name.lower().replace(' ', '')}.com",
            legal_name=name,
            created_at=base_time + timedelta(days=i),
            updated_at=base_time + timedelta(days=i),
        )
        db.add(a)
        apps.append(a)
    db.commit()
    return apps


def test_applications_sort_by_company_name_asc(db_session):
    _seed_applications(db_session)
    admin = _make_user(UserRole.channel_ops_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/applications?sort_by=company_name&sort_dir=asc")
        assert r.status_code == 200, r.text
        names = [a["legal_name"] for a in r.json()["items"]]
        assert names == ["Alpha Co", "Bravo Co", "Charlie Co"]

        # program_type is intentionally NOT in the allowlist -> falls back
        r = client.get("/applications?sort_by=program_type&sort_dir=asc")
        assert r.status_code == 200
    finally:
        _clear_overrides()


# ------------------ /internal/partners smoke ------------------


def test_internal_partners_sort_by_legal_name_asc(db_session):
    _make_org(db_session, name="Zeta Partners")
    _make_org(db_session, name="Alpha Partners")
    _make_org(db_session, name="Mike Partners")
    admin = _make_user(UserRole.channel_ops_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/partners?sort_by=legal_name&sort_dir=asc&page_size=200")
        assert r.status_code == 200
        names = [p["legal_name"] for p in r.json()["items"]]
        # Three fixture orgs + any orgs seeded by earlier tests in this module
        # -- assert that ours appear in the right relative order.
        idx = {n: i for i, n in enumerate(names)}
        assert idx["Alpha Partners"] < idx["Mike Partners"] < idx["Zeta Partners"]
    finally:
        _clear_overrides()


# ------------------ /internal/users smoke ------------------


def test_internal_users_sort_by_email_asc(db_session):
    admin = _make_user(UserRole.system_admin)
    admin.email = "aaa-admin@test.com"
    db_session.add(admin)
    other = User(
        id=uuid.uuid4(), email="zzz-ops@test.com", hashed_password="x",
        role=UserRole.channel_ops_admin.value, is_active=True,
    )
    db_session.add(other)
    db_session.commit()
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/users?sort_by=email&sort_dir=asc")
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["items"]]
        # Find our two seeded users' positions
        idx = {e: i for i, e in enumerate(emails)}
        assert idx["aaa-admin@test.com"] < idx["zzz-ops@test.com"]

        r = client.get("/internal/users?sort_by=nuke&sort_dir=asc")
        assert r.status_code == 200
    finally:
        _clear_overrides()


# ------------------ /internal/partner-users smoke ------------------


def test_internal_partner_users_sort_by_email_asc(db_session):
    org = _make_org(db_session, name="Partner Users Co")
    admin = _make_user(UserRole.channel_ops_admin)
    u1 = User(
        id=uuid.uuid4(), email="aaaa-partner@test.com", hashed_password="x",
        role=UserRole.partner_admin.value, partner_org_id=org.id, is_active=True,
    )
    u2 = User(
        id=uuid.uuid4(), email="zzzz-partner@test.com", hashed_password="x",
        role=UserRole.partner_user.value, partner_org_id=org.id, is_active=True,
    )
    db_session.add_all([u1, u2])
    db_session.commit()
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get("/internal/partner-users?sort_by=email&sort_dir=asc&page_size=200")
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["items"]]
        idx = {e: i for i, e in enumerate(emails)}
        assert idx["aaaa-partner@test.com"] < idx["zzzz-partner@test.com"]

        # partner_org sort works via the outer join -- just confirm no crash
        r = client.get("/internal/partner-users?sort_by=partner_org&sort_dir=asc&page_size=200")
        assert r.status_code == 200
    finally:
        _clear_overrides()


# ------------------ /partners/{id}/documents smoke ------------------


def test_partner_documents_sort_by_type_asc(db_session):
    org = _make_org(db_session, name="Docs Co")
    admin = _make_user(UserRole.channel_ops_admin)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    for i, doc_type in enumerate(["nda", "fiscal_id", "insurance"]):
        d = PartnerDocument(
            id=uuid.uuid4(),
            partner_org_id=org.id,
            uploaded_by_user_id=admin.id,
            document_type=doc_type,
            document_name=f"{doc_type}.pdf",
            file_path=f"/uploads/{doc_type}.pdf",
            status="pending_review",
            uploaded_at=base_time + timedelta(days=i),
        )
        db_session.add(d)
    db_session.commit()
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        r = client.get(f"/partners/{org.id}/documents?sort_by=document_type&sort_dir=asc")
        assert r.status_code == 200, r.text
        types = [d["document_type"] for d in r.json()["items"]]
        assert types == ["fiscal_id", "insurance", "nda"]

        r = client.get(f"/partners/{org.id}/documents?sort_by=nope&sort_dir=asc")
        assert r.status_code == 200
    finally:
        _clear_overrides()


# ------------------ Quotes endpoints smoke ------------------
# Quotes have heavy setup (Quote + QuoteVersion + DealRegistration +
# PartnerOrganization joins), so the deep ordering proof rides on
# /internal/deals. Here we just confirm the sort_by/sort_dir params are
# accepted and the response shape is unchanged on both endpoints.


def test_internal_quotes_accepts_sort_params(db_session):
    admin = _make_user(UserRole.system_admin)
    _override_user(db_session, admin)
    client = TestClient(app)
    try:
        for sort_by in ("quote_name", "deal_name", "partner_org", "feature_plan",
                        "grand_total_after_discount", "status", "created_at", "garbage"):
            r = client.get(f"/internal/quotes?sort_by={sort_by}&sort_dir=asc")
            assert r.status_code == 200, f"{sort_by}: {r.text}"
            body = r.json()
            assert "items" in body and "total" in body
    finally:
        _clear_overrides()


def test_partner_quotes_accepts_sort_params(db_session):
    org = _make_org(db_session, name="Partner Quotes Co")
    user = _make_user(UserRole.partner_admin, partner_org_id=org.id)
    _override_user(db_session, user)
    client = TestClient(app)
    try:
        for sort_by in ("quote_name", "deal_name", "feature_plan",
                        "grand_total_after_discount", "status", "created_at", "junk"):
            r = client.get(f"/partners/{org.id}/quotes?sort_by={sort_by}&sort_dir=desc")
            assert r.status_code == 200, f"{sort_by}: {r.text}"
            assert "items" in r.json()
    finally:
        _clear_overrides()
