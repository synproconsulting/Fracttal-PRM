"""create document_references join table

Revision ID: 035
Revises: 034
Create Date: 2026-05-27

Sprint 21 / AD-33 -- per-document cross-record links. A single
``partner_documents`` row may be referenced by multiple workflow objects
(e.g. one signed-order document referenced both as the deal's contract
attachment and as a quote acceptance proof). The join table stores those
links without duplicating file bytes.

Columns
-------
``entity_type`` -- polymorphic discriminator (``quote`` | ``quote_version``
| ``deal`` | ``application`` | ...). No FK constraint -- a union-typed FK
would require non-portable triggers.

``entity_id`` -- the target object's UUID.

``label`` -- semantic tag such as ``quote_acceptance``, ``purchase_order``,
``signed_proposal``. Free-form string so taxonomy can grow without
schema changes.

Indexes
-------
``ix_doc_refs_entity`` -- fast lookup of references for a given object
(used by the quote acceptance gate in Sprint 21).

``ix_doc_refs_document`` -- fast lookup of references for a given
document (used by the "View References" panel).

Idempotent: existence check on the table name and ``IF NOT EXISTS`` on
each index.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'document_references' in existing:
        return

    op.create_table(
        'document_references',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'document_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column(
            'entity_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['document_id'],
            ['partner_documents.id'],
            ondelete='CASCADE',
        ),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_refs_entity "
        "ON document_references (entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_refs_document "
        "ON document_references (document_id)"
    )


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS ix_doc_refs_document")
    except Exception:
        pass
    try:
        op.execute("DROP INDEX IF EXISTS ix_doc_refs_entity")
    except Exception:
        pass
    try:
        op.drop_table('document_references')
    except Exception:
        pass
