"""create document_types table + seed + alter partner_documents.document_type to VARCHAR

Revision ID: 017
Revises: 016
Create Date: 2026-05-17

Sprint 9 / FPRM-144 — Document type values are admin-configurable.

The legacy ``DocumentType`` Python enum was mapped to a PostgreSQL ENUM type
in migration 005. This migration:

1. Creates ``document_types`` (id, code, label, is_active, timestamps).
2. Seeds it with the 10 original enum values.
3. Converts ``partner_documents.document_type`` from the PG enum to VARCHAR
   (same pattern as 015) and drops the now-unused enum type.

Upload validation moves from the Python enum to a query against this table
(``documents_router.upload_document``), enabling system_admins to add new
document categories at runtime via POST /config/document-types.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


SEED_VALUES = [
    ("id_legal_representative", "ID of legal representative"),
    ("power_of_attorney", "Power of attorney"),
    ("articles_of_incorporation", "Articles of incorporation"),
    ("beneficial_owners_list", "Beneficial owners list"),
    ("fiscal_id", "Fiscal ID"),
    ("proof_of_fiscal_domicile", "Proof of fiscal domicile"),
    ("bank_certificate", "Bank certificate"),
    ("nda", "NDA"),
    ("insurance", "Insurance"),
    ("other", "Other"),
]


def upgrade() -> None:
    op.create_table(
        'document_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_document_types_code', 'document_types', ['code'], unique=True)

    # Seed canonical values
    for code, label in SEED_VALUES:
        op.execute(sa.text(
            "INSERT INTO document_types (id, code, label, is_active, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :code, :label, true, now(), now())"
        ).bindparams(code=code, label=label))

    # Convert partner_documents.document_type from ENUM to VARCHAR.
    # Existing rows are preserved because the enum labels are valid strings.
    op.execute(
        "ALTER TABLE partner_documents "
        "ALTER COLUMN document_type TYPE VARCHAR "
        "USING document_type::text"
    )
    op.execute("DROP TYPE IF EXISTS document_type")


def downgrade() -> None:
    op.execute(
        "CREATE TYPE document_type AS ENUM ("
        "'id_legal_representative','power_of_attorney','articles_of_incorporation',"
        "'beneficial_owners_list','fiscal_id','proof_of_fiscal_domicile',"
        "'bank_certificate','nda','insurance','other')"
    )
    op.execute(
        "ALTER TABLE partner_documents "
        "ALTER COLUMN document_type TYPE document_type "
        "USING document_type::document_type"
    )
    op.drop_index('ix_document_types_code', table_name='document_types')
    op.drop_table('document_types')
