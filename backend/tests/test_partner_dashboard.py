"""FPRM-183 — tests for GET /partners/{id}/dashboard/summary."""
import os
import sys
import uuid
from datetime import date

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
    DocumentStatus,
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerDocument,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    User,
)
from roles import UserRole


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        "sqlite:///./test_partner_dashboard.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_partner_dashboard.db"):
        try:
            os.remove("./test_partner_dashboard.db")
        except OSError:
            pass


@pytest.fixture()
def db_session(test_engine):
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _make_org(db_session) -> PartnerOrganization:
    org = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name="Acme Co",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.master,
        status=PartnerStatus.active,
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_user(db_session, role: str, partner_org_id=None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name="U",
        role=role,
        is_active=True,
        partner_org_id=partner_org_id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_deal(db_session, partner_org_id, status: str) -> DealRegistration:
    deal = DealRegistration(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        status=status,
        customer_name="C",
        deal_name=f"D {uuid.uuid4().hex[:4]}",
        estimated_close_date=date.today(),
    )
    db_session.add(deal)
    db_session.commit()
    return deal


def _make_checklist(db_session, partner_org_id, **overrides) -> PartnerActivationChecklist:
    fields = dict(
        profile_complete=False,
        documents_uploaded=False,
        terms_signed=False,
        baseline_training_complete=False,
        activation_complete=False,
    )
    fields.update(overrides)
    checklist = PartnerActivationChecklist(
        id=uuid.uuid4(), partner_org_id=partner_org_id, **fields,
    )
    db_session.add(checklist)
    db_session.commit()
    return checklist


def _make_document(db_session, partner_org_id, uploaded_by_user_id, status: DocumentStatus) -> PartnerDocument:
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=partner_org_id,
        document_type="nda",
        document_name=f"doc-{uuid.uuid4().hex[:4]}",
        file_path="/tmp/x",
        uploaded_by_user_id=uploaded_by_user_id,
        status=status,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


def test_summary_zero_state_no_checklist(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    body = client.get(f"/partners/{org.id}/dashboard/summary").json()
    assert body["deals"] == {"draft": 0, "submitted": 0, "under_review": 0, "approved": 0, "info_required": 0}
    assert body["activation"] == {"complete": False, "items_complete": 0, "items_total": 4}
    assert body["documents"] == {"pending_review": 0, "approved": 0, "rejected": 0}


def test_summary_counts_deals_by_status(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    _make_deal(db_session, org.id, "draft")
    _make_deal(db_session, org.id, "draft")
    _make_deal(db_session, org.id, "submitted")
    _make_deal(db_session, org.id, "under_review")
    _make_deal(db_session, org.id, "approved")
    _make_deal(db_session, org.id, "info_required")
    _make_deal(db_session, org.id, "rejected")  # not in dashboard buckets

    deals = client.get(f"/partners/{org.id}/dashboard/summary").json()["deals"]
    assert deals == {"draft": 2, "submitted": 1, "under_review": 1, "approved": 1, "info_required": 1}


def test_summary_activation_partial_progress(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    _make_checklist(db_session, org.id, profile_complete=True, terms_signed=True)
    activation = client.get(f"/partners/{org.id}/dashboard/summary").json()["activation"]
    assert activation == {"complete": False, "items_complete": 2, "items_total": 4}


def test_summary_activation_complete(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    _make_checklist(
        db_session, org.id,
        profile_complete=True, documents_uploaded=True, terms_signed=True,
        baseline_training_complete=True, activation_complete=True,
    )
    activation = client.get(f"/partners/{org.id}/dashboard/summary").json()["activation"]
    assert activation == {"complete": True, "items_complete": 4, "items_total": 4}


def test_summary_counts_documents_by_status(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    _make_document(db_session, org.id, admin.id, DocumentStatus.pending_review)
    _make_document(db_session, org.id, admin.id, DocumentStatus.pending_review)
    _make_document(db_session, org.id, admin.id, DocumentStatus.approved)
    _make_document(db_session, org.id, admin.id, DocumentStatus.rejected)
    _make_document(db_session, org.id, admin.id, DocumentStatus.expired)  # not in dashboard

    docs = client.get(f"/partners/{org.id}/dashboard/summary").json()["documents"]
    assert docs == {"pending_review": 2, "approved": 1, "rejected": 1}


def test_summary_isolates_other_orgs_data(client, db_session):
    """Counts must be scoped to the partner_org_id, not all rows."""
    own_org = _make_org(db_session)
    other_org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=own_org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Data in other org should not leak
    _make_deal(db_session, other_org.id, "submitted")
    _make_deal(db_session, other_org.id, "submitted")
    _make_deal(db_session, own_org.id, "submitted")
    _make_document(db_session, other_org.id, admin.id, DocumentStatus.approved)

    body = client.get(f"/partners/{own_org.id}/dashboard/summary").json()
    assert body["deals"]["submitted"] == 1  # only own org's
    assert body["documents"]["approved"] == 0


def test_summary_404_for_unknown_partner(client, db_session):
    org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get(f"/partners/{uuid.uuid4()}/dashboard/summary")
    assert response.status_code == 404


def test_summary_403_for_other_partner_org(client, db_session):
    org = _make_org(db_session)
    other_org = _make_org(db_session)
    admin = _make_user(db_session, UserRole.partner_admin.value, partner_org_id=other_org.id)
    app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get(f"/partners/{org.id}/dashboard/summary")
    assert response.status_code == 403
    assert "not your organisation" in response.json()["detail"].lower()


def test_summary_403_for_non_partner_admin_role(client, db_session):
    org = _make_org(db_session)
    user = _make_user(db_session, UserRole.partner_user.value, partner_org_id=org.id)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get(f"/partners/{org.id}/dashboard/summary")
    assert response.status_code == 403
    assert "partner_admin" in response.json()["detail"]


def test_summary_200_for_system_admin_any_org(client, db_session):
    """FPRM-190: system_admin can view any partner's dashboard summary."""
    org = _make_org(db_session)
    _make_deal(db_session, org.id, "submitted")
    admin = _make_user(db_session, UserRole.system_admin.value)
    app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get(f"/partners/{org.id}/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["deals"]["submitted"] == 1


def test_summary_200_for_channel_manager_any_org(client, db_session):
    """FPRM-190: channel_manager can view any partner's dashboard summary."""
    org = _make_org(db_session)
    user = _make_user(db_session, UserRole.channel_manager.value)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get(f"/partners/{org.id}/dashboard/summary")
    assert response.status_code == 200


def test_summary_200_for_channel_ops_admin_any_org(client, db_session):
    """FPRM-190: channel_ops_admin can view any partner's dashboard summary."""
    org = _make_org(db_session)
    user = _make_user(db_session, UserRole.channel_ops_admin.value)
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get(f"/partners/{org.id}/dashboard/summary")
    assert response.status_code == 200
