"""create quote_documents table

Revision ID: 033
Revises: 032
Create Date: 2026-05-21

Adds the ``quote_documents`` table -- evidence files attached to a quote
(proof-of-acceptance, purchase order, signed proposal, other). Base64-encoded
bytes live in ``file_data`` per AD-17 so uploads survive a Railway redeploy.

Acceptance gate: the application layer (PATCH /quotes/{id}/status) requires
at least one ``document_type='quote_acceptance'`` row before letting a quote
transition to ``accepted``. The migration itself only creates schema; the
business rule lives in the router.

Idempotent: existence check on the table name, ``IF NOT EXISTS`` on the
index, so re-running on a partially-applied database is a no-op.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'quote_documents' not in existing:
        op.create_table(
            'quote_documents',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('document_type', sa.String(), nullable=False),
            sa.Column('file_name', sa.String(), nullable=False),
            sa.Column('file_data', sa.Text(), nullable=False),
            sa.Column('file_size_bytes', sa.Integer(), nullable=False),
            sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('uploaded_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['quote_id'], ['quotes.id']),
            sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_quote_documents_quote_id "
            "ON quote_documents (quote_id)"
        )


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS ix_quote_documents_quote_id")
    except Exception:
        pass
    try:
        op.drop_table('quote_documents')
    except Exception:
        pass
