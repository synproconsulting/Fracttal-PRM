"""Sprint 23 PR A -- seed canonical document types into BOTH tables + reconcile

Revision ID: 039
Revises: 038
Create Date: 2026-05-29

Data-only migration (no schema change). Establishes the two-table document
model (AD-38):

* ``document_types``      -- the *vocabulary* (code, label, is_active). This is
  what the upload-form / admin dropdowns list and what upload validation checks.
* ``document_type_rules`` -- the *approval policy* per type (requires_approval,
  auto_approve). Drives the upload status + the acceptance gate.

Seeds the canonical KYC + contract set into BOTH tables with the SAME key, so
every seeded type is both selectable (vocabulary) and governed (rule):

| type                      | label                     | requires_approval | auto_approve |
|---------------------------|---------------------------|-------------------|--------------|
| proof_of_fiscal_domicile  | Proof of Fiscal Domicile  | true              | false        |
| w9                        | W-9                       | true              | false        |
| insurance_certificate     | Insurance Certificate     | true              | false        |
| nda                       | NDA                       | true              | false        |
| security_assessment       | Security Assessment       | true              | false        |
| contract                  | Contract                  | (rule from 038)   | (from 038)   |
| quote_acceptance          | Quote Acceptance          | (rule from 038)   | (from 038)   |

``contract`` and ``quote_acceptance`` already have rules from migration 038 --
this migration only ensures they ALSO exist in the ``document_types`` vocabulary
(adds if missing), and never touches the 038 rule rows.

Reconcile: for every DISTINCT ``document_type`` already present in
``partner_documents``, ensure a vocabulary row AND a default rule
(``requires_approval=true, auto_approve=false``) exist, so no existing data is
left ungoverned or unselectable.

Idempotent: every insert uses ``WHERE NOT EXISTS`` so a re-run is a no-op.
``downgrade()`` removes ONLY the five rule rows this migration introduced
(never the 038 rows, never reconciled in-use rows, never vocabulary rows that
may pre-date this migration).
"""
from alembic import op
import sqlalchemy as sa


revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None


# (code, label) seeded into the document_types vocabulary.
SEED_VOCAB = [
    ('proof_of_fiscal_domicile', 'Proof of Fiscal Domicile'),
    ('w9', 'W-9'),
    ('insurance_certificate', 'Insurance Certificate'),
    ('nda', 'NDA'),
    ('security_assessment', 'Security Assessment'),
    ('contract', 'Contract'),
    ('quote_acceptance', 'Quote Acceptance'),
]

# Rules introduced by THIS migration (requires_approval=true, auto_approve=false).
# contract + quote_acceptance rules already exist from 038 and are left alone.
SEED_RULES = [
    'proof_of_fiscal_domicile',
    'w9',
    'insurance_certificate',
    'nda',
    'security_assessment',
]


def _dialect_bits(bind):
    """Return (id_expr, true_literal, false_literal, now_expr) for the dialect."""
    if bind.dialect.name == 'postgresql':
        return "gen_random_uuid()", "true", "false", "NOW()"
    # sqlite (tests) + others
    return "lower(hex(randomblob(16)))", "1", "0", "CURRENT_TIMESTAMP"


def _ensure_vocab(bind, code, label, idexpr, true_lit, now):
    bind.execute(
        sa.text(
            f"INSERT INTO document_types (id, code, label, is_active, created_at, updated_at) "
            f"SELECT {idexpr}, :code, :label, {true_lit}, {now}, {now} "
            f"WHERE NOT EXISTS (SELECT 1 FROM document_types WHERE code = :code)"
        ).bindparams(code=code, label=label)
    )


def _ensure_rule(bind, doc_type, idexpr, true_lit, false_lit, now, description=None):
    bind.execute(
        sa.text(
            f"INSERT INTO document_type_rules "
            f"(id, document_type, requires_approval, auto_approve, description, created_at, updated_at) "
            f"SELECT {idexpr}, :dt, {true_lit}, {false_lit}, :desc, {now}, {now} "
            f"WHERE NOT EXISTS (SELECT 1 FROM document_type_rules WHERE document_type = :dt)"
        ).bindparams(dt=doc_type, desc=description)
    )


def upgrade() -> None:
    bind = op.get_bind()
    idexpr, true_lit, false_lit, now = _dialect_bits(bind)

    # 1. Seed the canonical vocabulary (both pre-existing and new codes).
    for code, label in SEED_VOCAB:
        _ensure_vocab(bind, code, label, idexpr, true_lit, now)

    # 2. Seed the KYC approval rules (contract/quote_acceptance already from 038).
    for doc_type in SEED_RULES:
        _ensure_rule(
            bind, doc_type, idexpr, true_lit, false_lit, now,
            description='KYC document -- requires manual approval',
        )

    # 3. Reconcile every in-use document_type: ensure both a vocabulary row
    #    and a default rule exist so no existing data is ungoverned.
    rows = bind.execute(
        sa.text(
            "SELECT DISTINCT document_type FROM partner_documents "
            "WHERE document_type IS NOT NULL AND document_type <> ''"
        )
    ).fetchall()
    for (doc_type,) in rows:
        label = str(doc_type).replace('_', ' ').title()
        _ensure_vocab(bind, doc_type, label, idexpr, true_lit, now)
        _ensure_rule(
            bind, doc_type, idexpr, true_lit, false_lit, now,
            description='Reconciled in-use type -- default requires approval',
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Remove only the five rule rows this migration introduced. The 038 rows
    # (contract, quote_acceptance), reconciled in-use rows, and all vocabulary
    # rows are intentionally left in place.
    for doc_type in SEED_RULES:
        bind.execute(
            sa.text(
                "DELETE FROM document_type_rules WHERE document_type = :dt"
            ).bindparams(dt=doc_type)
        )
