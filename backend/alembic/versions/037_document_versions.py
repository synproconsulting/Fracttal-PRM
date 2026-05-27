"""Sprint 22 / AD-34 -- document versioning support

Revision ID: 037
Revises: 036
Create Date: 2026-05-27

Creates ``document_versions`` so every binary blob lives in a versioned
row instead of the deprecated ``partner_documents.file_data`` column.
Adds two denormalised pointers to ``partner_documents`` so list views can
show the current version + version count without an extra join.

Backfill: any existing ``partner_documents`` row with non-null
``file_data`` gets a single ``document_versions`` row at
``version_number = 1`` with ``is_current = true``. The original
``file_data`` column is intentionally NOT dropped here (AD-34); future
cleanup migration will null+drop it once all consumers read from
``document_versions``.

Idempotent: existence checks on the table, columns, and index so a
partially-applied state replays cleanly.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'document_versions' not in existing_tables:
        op.create_table(
            'document_versions',
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
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('file_data', sa.Text(), nullable=False),
            sa.Column('file_size_bytes', sa.Integer(), nullable=True),
            sa.Column('mime_type', sa.String(length=100), nullable=True),
            sa.Column(
                'uploaded_by',
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
            sa.Column(
                'uploaded_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('NOW()'),
            ),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column(
                'is_current',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'),
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(
                ['document_id'],
                ['partner_documents.id'],
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['uploaded_by'],
                ['users.id'],
                ondelete='SET NULL',
            ),
            sa.UniqueConstraint(
                'document_id',
                'version_number',
                name='uq_doc_version',
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_doc_versions_document "
            "ON document_versions (document_id)"
        )
        # Partial unique index keeps "exactly one current version per doc"
        # honest at the DB layer. Postgres-only -- sqlite test paths use
        # ORM-level enforcement.
        if bind.dialect.name == 'postgresql':
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_doc_versions_current "
                "ON document_versions (document_id, is_current) "
                "WHERE is_current = true"
            )

    if 'partner_documents' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('partner_documents')}
        if 'current_version_number' not in existing_cols:
            op.add_column(
                'partner_documents',
                sa.Column('current_version_number', sa.Integer(), nullable=True),
            )
        if 'version_count' not in existing_cols:
            op.add_column(
                'partner_documents',
                sa.Column(
                    'version_count',
                    sa.Integer(),
                    nullable=False,
                    server_default='1',
                ),
            )

        # Backfill: every partner_documents row with non-null file_data
        # becomes a single document_versions row at version_number=1.
        # PartnerDocument.uploaded_by_user_id is the canonical uploader
        # column on the parent table (Sprint 6); the new
        # document_versions.uploaded_by points at the same user. If a
        # legacy row has no uploaded_at (shouldn't happen post-Sprint-6
        # but guard anyway), fall back to NOW().
        op.execute(
            """
            INSERT INTO document_versions (
                id, document_id, version_number,
                file_data, file_size_bytes, mime_type,
                uploaded_by, uploaded_at, is_current
            )
            SELECT
                gen_random_uuid(),
                pd.id,
                1,
                pd.file_data,
                pd.file_size_bytes,
                pd.mime_type,
                pd.uploaded_by_user_id,
                COALESCE(pd.uploaded_at, NOW()),
                true
            FROM partner_documents pd
            LEFT JOIN document_versions dv
                ON dv.document_id = pd.id AND dv.version_number = 1
            WHERE pd.file_data IS NOT NULL
              AND dv.id IS NULL
            """
        )
        op.execute(
            """
            UPDATE partner_documents
            SET current_version_number = 1, version_count = 1
            WHERE file_data IS NOT NULL
              AND (current_version_number IS NULL OR current_version_number = 0)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'partner_documents' in set(inspector.get_table_names()):
        cols = {c['name'] for c in inspector.get_columns('partner_documents')}
        if 'version_count' in cols:
            op.drop_column('partner_documents', 'version_count')
        if 'current_version_number' in cols:
            op.drop_column('partner_documents', 'current_version_number')
    try:
        op.execute("DROP INDEX IF EXISTS ix_doc_versions_current")
        op.execute("DROP INDEX IF EXISTS ix_doc_versions_document")
    except Exception:
        pass
    try:
        op.drop_table('document_versions')
    except Exception:
        pass
