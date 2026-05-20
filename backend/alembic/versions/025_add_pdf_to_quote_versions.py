"""add pdf storage columns to quote_versions

Revision ID: 025
Revises: 024
Create Date: 2026-05-19

Sprint 16 / FPRM-258 - Adds three columns to quote_versions for storing
the generated PDF artefact (base64-encoded), the generation timestamp,
and the filename.

AD-17 (added in Sprint 16): Railway does not provide persistent file
storage across deploys, so PDF artefacts are stored as base64-encoded
Text columns rather than on local disk.

Idempotent - existence checks before adding columns.
"""
from alembic import op
import sqlalchemy as sa


revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c['name'] for c in inspector.get_columns('quote_versions')}

    if 'pdf_artifact_data' not in existing_cols:
        op.add_column('quote_versions', sa.Column('pdf_artifact_data', sa.Text(), nullable=True))
    if 'pdf_generated_at' not in existing_cols:
        op.add_column('quote_versions', sa.Column('pdf_generated_at', sa.DateTime(), nullable=True))
    if 'pdf_filename' not in existing_cols:
        op.add_column('quote_versions', sa.Column('pdf_filename', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('quote_versions', 'pdf_filename')
    op.drop_column('quote_versions', 'pdf_generated_at')
    op.drop_column('quote_versions', 'pdf_artifact_data')
