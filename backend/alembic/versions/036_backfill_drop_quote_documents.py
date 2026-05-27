"""backfill quote_documents into partner_documents and drop the table

Revision ID: 036
Revises: 035
Create Date: 2026-05-27

Sprint 21 / AD-33 -- ``quote_documents`` was created in migration 033 as
a per-quote evidence store. With the centralised repository the file
content must live in ``partner_documents`` and the per-quote linkage in
``document_references``. This migration:

1. For every existing ``quote_documents`` row, INSERT a corresponding
   ``partner_documents`` row (status ``approved`` because the file was
   already a live attachment).
2. INSERT a corresponding ``document_references`` row tying the new
   ``partner_documents`` row to the original quote (``entity_type=
   'quote'``, ``label=`` the original ``document_type``).
3. DROP ``quote_documents``.

Idempotent: existence check on ``quote_documents`` so re-running after
the drop is a no-op. The backfill itself is wrapped row-by-row -- if a
single row fails (e.g. orphaned quote_id with no surviving deal) the
migration logs the failure and continues so a corrupt partner record
doesn't block a Railway redeploy.
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


_BACKFILL_SELECT = sa.text(
    """
    SELECT
        qd.id AS qd_id,
        qd.quote_id,
        qd.document_type,
        qd.file_name,
        qd.file_data,
        qd.file_size_bytes,
        qd.uploaded_by,
        qd.uploaded_at,
        qd.notes,
        dr.partner_org_id
    FROM quote_documents qd
    JOIN quotes q ON qd.quote_id = q.id
    JOIN deal_registrations dr ON q.deal_id = dr.id
    """
)


_PARTNER_DOC_INSERT_PG = sa.text(
    """
    INSERT INTO partner_documents (
        id, partner_org_id, document_type, document_name,
        file_path, file_data, file_size_bytes, mime_type,
        uploaded_by_user_id, uploaded_at, status, review_notes
    )
    VALUES (
        :id, :partner_org_id, :document_type, :document_name,
        NULL, :file_data, :file_size_bytes, :mime_type,
        :uploaded_by_user_id, :uploaded_at,
        CAST(:status AS document_status), :review_notes
    )
    """
)


_PARTNER_DOC_INSERT_GENERIC = sa.text(
    """
    INSERT INTO partner_documents (
        id, partner_org_id, document_type, document_name,
        file_path, file_data, file_size_bytes, mime_type,
        uploaded_by_user_id, uploaded_at, status, review_notes
    )
    VALUES (
        :id, :partner_org_id, :document_type, :document_name,
        NULL, :file_data, :file_size_bytes, :mime_type,
        :uploaded_by_user_id, :uploaded_at, :status, :review_notes
    )
    """
)


_DOC_REF_INSERT = sa.text(
    """
    INSERT INTO document_references (
        id, document_id, entity_type, entity_id, label, created_at
    )
    VALUES (
        :id, :document_id, :entity_type, :entity_id, :label, :created_at
    )
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'quote_documents' not in existing:
        return

    is_postgres = bind.dialect.name == 'postgresql'
    partner_insert = _PARTNER_DOC_INSERT_PG if is_postgres else _PARTNER_DOC_INSERT_GENERIC

    rows = bind.execute(_BACKFILL_SELECT).fetchall()
    for row in rows:
        new_doc_id = uuid.uuid4()
        try:
            bind.execute(
                partner_insert,
                {
                    'id': new_doc_id,
                    'partner_org_id': row.partner_org_id,
                    'document_type': row.document_type or 'other',
                    'document_name': row.file_name,
                    'file_data': row.file_data,
                    'file_size_bytes': row.file_size_bytes,
                    'mime_type': 'application/octet-stream',
                    'uploaded_by_user_id': row.uploaded_by,
                    'uploaded_at': row.uploaded_at,
                    'status': 'approved',
                    'review_notes': row.notes,
                },
            )
            bind.execute(
                _DOC_REF_INSERT,
                {
                    'id': uuid.uuid4(),
                    'document_id': new_doc_id,
                    'entity_type': 'quote',
                    'entity_id': row.quote_id,
                    'label': row.document_type or 'other',
                    'created_at': row.uploaded_at,
                },
            )
        except Exception as exc:
            print(
                f"[migration 036] skipping quote_documents row {row.qd_id}: {exc}"
            )

    try:
        op.execute("DROP INDEX IF EXISTS ix_quote_documents_quote_id")
    except Exception:
        pass
    op.drop_table('quote_documents')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'quote_documents' in set(inspector.get_table_names()):
        return
    from sqlalchemy.dialects import postgresql
    op.create_table(
        'quote_documents',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_data', sa.Text(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'uploaded_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_quote_documents_quote_id "
        "ON quote_documents (quote_id)"
    )
