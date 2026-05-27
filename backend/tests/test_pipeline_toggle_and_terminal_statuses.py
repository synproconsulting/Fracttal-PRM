"""Migration 032 + cancelled/lost/withdrawn terminal status tests.

Covers the spec acceptance list:

* draft -> cancelled allowed
* sent -> cancelled allowed
* accepted -> cancelled NOT allowed (422)
* approved -> lost allowed; audit event logged
* approved -> withdrawn allowed
* submitted -> withdrawn allowed
* include_in_pipeline toggle updates correctly
* Pipeline total excludes cancelled quotes
* Pipeline total excludes quotes with include_in_pipeline = False
* Lost/withdrawn deals excluded from pipeline report counts

Uses an isolated sqlite file plus a fresh schema per fixture so we can
exercise the new columns without colliding with other test modules.
"""
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
    AuditLog,
    DealRegistration,
    DocumentReference,
    DocumentStatus,
    FeaturePlanPrice,
    PartnerActivationChecklist,
    PartnerCategory,
    PartnerDocument,
    PartnerOrganization,
    PartnerStatus,
    ProgramType,
    Quote,
    User,
    VolumeDiscountTier,
)
from roles import UserRole


DB_PATH = "./test_pipeline_toggle.db"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        _seed_pricing(s)
        yield s
    finally:
        s.rollback()
        for tbl in (
            "document_references", "partner_documents",
            "quote_line_items", "quote_versions", "quotes",
            "addon_catalog_items", "volume_discount_tiers", "feature_plan_prices",
            "partner_activation_checklists",
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


def _seed_pricing(db):
    today = date(2024, 1, 1)
    db.add_all([
        FeaturePlanPrice(plan_code="starter", feature_pack_annual=Decimal("1161.00"),
                         transactional_user_annual=Decimal("540.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="professional", feature_pack_annual=Decimal("2868.00"),
                         transactional_user_annual=Decimal("720.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
        FeaturePlanPrice(plan_code="enterprise", feature_pack_annual=Decimal("8028.00"),
                         transactional_user_annual=Decimal("900.00"),
                         limited_tech_user_annual=Decimal("240.00"),
                         effective_from=today),
    ])
    db.add_all([
        VolumeDiscountTier(min_users=1, max_users=10, transactional_user_discount_pct=Decimal("0"), limited_tech_user_discount_pct=Decimal("0")),
        VolumeDiscountTier(min_users=11, max_users=50, transactional_user_discount_pct=Decimal("30"), limited_tech_user_discount_pct=Decimal("30")),
        VolumeDiscountTier(min_users=51, max_users=100, transactional_user_discount_pct=Decimal("40"), limited_tech_user_discount_pct=Decimal("40")),
        VolumeDiscountTier(min_users=101, max_users=300, transactional_user_discount_pct=Decimal("50"), limited_tech_user_discount_pct=Decimal("50")),
        VolumeDiscountTier(min_users=301, max_users=500, transactional_user_discount_pct=Decimal("60"), limited_tech_user_discount_pct=Decimal("60")),
        VolumeDiscountTier(min_users=501, max_users=None, transactional_user_discount_pct=Decimal("70"), limited_tech_user_discount_pct=Decimal("70")),
    ])
    db.commit()


def _org(db, *, status=PartnerStatus.active):
    o = PartnerOrganization(
        id=uuid.uuid4(),
        legal_name=f"Org {uuid.uuid4().hex[:4]}",
        program_type=ProgramType.distributor,
        partner_category=PartnerCategory.reseller,
        status=status,
    )
    db.add(o); db.commit()
    return o


def _deal(db, org_id, *, status="approved"):
    d = DealRegistration(
        id=uuid.uuid4(), partner_org_id=org_id, status=status,
        customer_name="C", deal_name=f"D-{uuid.uuid4().hex[:4]}",
        estimated_deal_value=Decimal("10000.00"),
    )
    db.add(d); db.commit()
    return d


def _user(db, role, org_id=None):
    u = User(
        id=uuid.uuid4(), email=f"{role}-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="x", role=role, is_active=True, partner_org_id=org_id,
    )
    db.add(u); db.commit()
    return u


def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _make_quote(client, deal_id):
    r = client.post(f"/deals/{deal_id}/quotes", json={
        "feature_plan": "starter",
        "qty_transactional_users": 1,
        "qty_limited_tech_users": 0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ============================================================
# Quote status transitions: cancelled
# ============================================================


def test_draft_to_cancelled_allowed(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    r = client.patch(f"/quotes/{qid}/status", json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_sent_to_cancelled_allowed(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    r = client.patch(f"/quotes/{qid}/status", json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_accepted_to_cancelled_not_allowed(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    # Sprint 21 / AD-33: seed the acceptance evidence in partner_documents.
    _seed_quote_acceptance(db_session, qid)
    client.patch(f"/quotes/{qid}/status", json={"status": "accepted"})
    r = client.patch(f"/quotes/{qid}/status", json={"status": "cancelled"})
    assert r.status_code == 422


def test_cancelled_is_terminal(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{qid}/status", json={"status": "cancelled"})
    # Any outbound transition from cancelled must 422
    for nxt in ("draft", "sent", "accepted", "expired"):
        r = client.patch(f"/quotes/{qid}/status", json={"status": nxt})
        assert r.status_code == 422, f"cancelled -> {nxt} should not be allowed"


# ============================================================
# Deal status transitions: lost / withdrawn
# ============================================================


def test_approved_to_lost_allowed_and_audit_logged(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="approved")
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "lost"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "lost"
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "deal.lost" in actions


def test_approved_to_withdrawn_allowed(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="approved")
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "withdrawn"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "withdrawn"
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "deal.withdrawn" in actions


def test_submitted_to_withdrawn_allowed(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="submitted")
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "withdrawn"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "withdrawn"


def test_under_review_to_withdrawn_allowed(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="under_review")
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "withdrawn"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "withdrawn"


def test_submitted_to_lost_not_allowed(client, db_session):
    # Spec: approved -> lost only. submitted -> lost is not allowed.
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="submitted")
    _auth(_user(db_session, UserRole.channel_manager.value))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "lost"})
    assert r.status_code == 422


def test_lost_is_terminal(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="approved")
    _auth(_user(db_session, UserRole.channel_manager.value))
    client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "lost"})
    # Try every recognised status -- all must 422 because lost is terminal.
    for nxt in ("approved", "submitted", "under_review", "withdrawn"):
        r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": nxt})
        assert r.status_code == 422, f"lost -> {nxt} should not be allowed"


def test_terminal_status_requires_review_role(client, db_session):
    org = _org(db_session)
    deal = _deal(db_session, org.id, status="approved")
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.patch(f"/deal-registrations/{deal.id}/status", json={"status": "lost"})
    assert r.status_code == 403


# ============================================================
# Pipeline inclusion toggle + pipeline_total filter
# ============================================================


def test_include_in_pipeline_toggle_updates_and_audits(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    # Default is False per migration 032
    body = client.get(f"/quotes/{qid}").json()
    assert body["include_in_pipeline"] is False
    # Flip to True
    r = client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    assert r.status_code == 200, r.text
    assert r.json()["include_in_pipeline"] is True
    # Flip back to False
    r = client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": False})
    assert r.status_code == 200
    assert r.json()["include_in_pipeline"] is False
    # Audit events for both flips
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert actions.count("quote.pipeline_inclusion_changed") == 2


def test_pipeline_total_excludes_quotes_not_in_pipeline(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q_in = _make_quote(client, _deal(db_session, org.id).id)
    q_out = _make_quote(client, _deal(db_session, org.id).id)
    # Only q_in is opted in
    client.patch(f"/quotes/{q_in}/pipeline-inclusion", json={"include_in_pipeline": True})
    r = client.get("/internal/quotes")
    s = r.json()["summary"]
    one_quote_total = float(client.get(f"/quotes/{q_in}").json()["active_version_data"]["grand_total_after_discount"])
    assert s["pipeline_total"] == round(one_quote_total, 2)
    # q_out exists but contributes zero because it never opted in
    assert s["total_quotes"] == 2


def test_pipeline_total_excludes_cancelled_quotes(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q1 = _make_quote(client, _deal(db_session, org.id).id)
    q2 = _make_quote(client, _deal(db_session, org.id).id)
    # Opt both in
    client.patch(f"/quotes/{q1}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q2}/pipeline-inclusion", json={"include_in_pipeline": True})
    # Cancel q2: draft -> cancelled directly
    client.patch(f"/quotes/{q2}/status", json={"status": "cancelled"})
    r = client.get("/internal/quotes")
    s = r.json()["summary"]
    one_quote_total = float(client.get(f"/quotes/{q1}").json()["active_version_data"]["grand_total_after_discount"])
    assert s["cancelled"] == 1
    # Only q1 contributes
    assert s["pipeline_total"] == round(one_quote_total, 2)


def test_pipeline_total_excludes_expired_quotes(client, db_session):
    # Regression -- expired exclusion existed before; make sure it still works
    # alongside the new include_in_pipeline gate.
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    q1 = _make_quote(client, _deal(db_session, org.id).id)
    q2 = _make_quote(client, _deal(db_session, org.id).id)
    client.patch(f"/quotes/{q1}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q2}/pipeline-inclusion", json={"include_in_pipeline": True})
    client.patch(f"/quotes/{q2}/status", json={"status": "sent"})
    client.patch(f"/quotes/{q2}/status", json={"status": "expired"})
    r = client.get("/internal/quotes")
    s = r.json()["summary"]
    one_quote_total = float(client.get(f"/quotes/{q1}").json()["active_version_data"]["grand_total_after_discount"])
    assert s["pipeline_total"] == round(one_quote_total, 2)


def test_pipeline_inclusion_requires_write_role(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    qid = _make_quote(client, _deal(db_session, org.id).id)
    # Switch to partner_admin and try to flip
    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.patch(f"/quotes/{qid}/pipeline-inclusion", json={"include_in_pipeline": True})
    assert r.status_code == 403


# ============================================================
# Pipeline report excludes lost / withdrawn deals
# ============================================================


def test_pipeline_report_excludes_lost_and_withdrawn(client, db_session):
    org = _org(db_session)
    cm = _user(db_session, UserRole.channel_manager.value)
    _auth(cm)
    # Three approved deals
    d_active = _deal(db_session, org.id, status="approved")
    d_lost = _deal(db_session, org.id, status="approved")
    d_withdrawn = _deal(db_session, org.id, status="approved")
    client.patch(f"/deal-registrations/{d_lost.id}/status", json={"status": "lost"})
    client.patch(f"/deal-registrations/{d_withdrawn.id}/status", json={"status": "withdrawn"})
    r = client.get("/internal/reports/pipeline")
    assert r.status_code == 200, r.text
    body = r.json()
    # Only the still-approved deal counts
    assert body["totals"]["total_deals"] == 1
    assert body["totals"]["approved"] == 1
    # Approved value is 10000 each; lost/withdrawn must not be in total_value
    assert body["totals"]["total_value"] == 10000.0
    # Verify by_partner reflects the same exclusion
    bp = body["by_partner"]
    assert len(bp) == 1
    assert bp[0]["total_deals"] == 1


# ============================================================
# Admin retract (accepted -> sent)
# ============================================================


def _seed_quote_acceptance(db_session, quote_id):
    """Sprint 21 / AD-33 helper: directly seed an approved partner_documents
    row plus a document_references link so the acceptance gate clears
    without going through the upload API."""
    quote = db_session.query(Quote).filter(Quote.id == uuid.UUID(str(quote_id))).first()
    assert quote is not None
    uploader = db_session.query(User).first()
    doc = PartnerDocument(
        id=uuid.uuid4(),
        partner_org_id=quote.partner_org_id,
        document_type="quote_acceptance",
        document_name="acceptance.pdf",
        file_data="JVBERi0xLjQKJSVFT0Y=",
        file_size_bytes=14,
        mime_type="application/pdf",
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.approved,
    )
    db_session.add(doc)
    db_session.flush()
    ref = DocumentReference(
        id=uuid.uuid4(),
        document_id=doc.id,
        entity_type="quote",
        entity_id=uuid.UUID(str(quote_id)),
        label="quote_acceptance",
    )
    db_session.add(ref)
    db_session.commit()
    return str(doc.id)


def _accept_a_quote(client, deal_id, db_session):
    """Helper: create a quote, attach the required acceptance document, and
    walk it to ``accepted``. Returns the quote id."""
    qid = _make_quote(client, deal_id)
    client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    _seed_quote_acceptance(db_session, qid)
    r_acc = client.patch(f"/quotes/{qid}/status", json={"status": "accepted"})
    assert r_acc.status_code == 200, r_acc.text
    return qid


def test_system_admin_can_retract_accepted_quote(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    qid = _accept_a_quote(client, deal.id, db_session)

    _auth(_user(db_session, UserRole.system_admin.value))
    r = client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"
    # Audit row must use the dedicated quote.retracted action so reporting
    # can tell a real status_changed apart from a corrective retract.
    from models import AuditLog
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "quote.retracted")
        .filter(AuditLog.object_id == uuid.UUID(qid))
        .first()
    )
    assert audit is not None
    assert audit.before_state == {"status": "accepted"}
    assert audit.after_state == {"status": "sent"}


def test_channel_manager_cannot_retract_accepted_quote(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    qid = _accept_a_quote(client, deal.id, db_session)

    # Still authed as channel_manager — attempt the retract.
    r = client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    assert r.status_code == 403
    assert "system_admin" in r.json()["detail"]
    # Quote must remain accepted.
    assert client.get(f"/quotes/{qid}").json()["status"] == "accepted"


def test_partner_admin_cannot_retract_accepted_quote(client, db_session):
    org = _org(db_session)
    _auth(_user(db_session, UserRole.channel_manager.value))
    deal = _deal(db_session, org.id)
    qid = _accept_a_quote(client, deal.id, db_session)

    _auth(_user(db_session, UserRole.partner_admin.value, org_id=org.id))
    r = client.patch(f"/quotes/{qid}/status", json={"status": "sent"})
    # partner_admin is blocked by the write-role check (403) BEFORE the
    # retract-specific check fires — either way the request must fail
    # and the quote stays accepted.
    assert r.status_code == 403
    assert client.get(f"/quotes/{qid}").json()["status"] == "accepted"
