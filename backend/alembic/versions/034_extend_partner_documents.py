"""extend partner_documents for centralised document repository

Revision ID: 034
Revises: 033
Create Date: 2026-05-27

Sprint 21 / AD-33 -- ``partner_documents`` becomes the single store for all
partner-scoped file content. Two changes:

1. Add ``file_data`` (Text, nullable) -- base64-encoded file bytes per
   AD-19. Nullable so legacy ``file_path``-only rows from pre-Sprint-21
   uploads remain valid; new uploads populate ``file_data`` instead.

2. Relax ``file_path`` to nullable -- centralised storage no longer
   requires an on-disk path. Existing values are preserved.

Idempotent: column existence checks via the SQLAlchemy inspector so
re-running on a partially-applied database is a no-op.
"""
from alembic import op
import sqlalchemy as sa


revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'partner_documents' not in set(inspector.get_table_names()):
        return

    cols = {c['name']: c for c in inspector.get_columns('partner_documents')}

    if 'file_data' not in cols:
        op.add_column(
            'partner_documents',
            sa.Column('file_data', sa.Text(), nullable=True),
        )

    file_path = cols.get('file_path')
    if file_path is not None and not file_path.get('nullable', False):
        op.alter_column(
            'partner_documents',
            'file_path',
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'partner_documents' not in set(inspector.get_table_names()):
        return

    cols = {c['name']: c for c in inspector.get_columns('partner_documents')}

    if 'file_path' in cols:
        op.alter_column(
            'partner_documents',
            'file_path',
            existing_type=sa.String(),
            nullable=False,
        )
    if 'file_data' in cols:
        op.drop_column('partner_documents', 'file_data')
