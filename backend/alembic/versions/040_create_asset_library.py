"""Sprint 23 PR B / AD-39 -- Asset Library tables

Revision ID: 040
Revises: 039
Create Date: 2026-05-29

Creates the marketing/enablement asset catalogue:

* ``asset_categories`` -- groupings (name unique, display_order, is_active).
* ``assets``           -- catalogue rows; binary stored base64 in
  ``file_data`` (AD-17/AD-19). ``file_data`` is never returned by list
  endpoints -- only the download endpoint streams the decoded bytes (AD-20).
* ``asset_download_logs`` -- one row per download (who + which partner org).

Idempotent: existence checks on each table so a partially-applied state
replays cleanly. ``downgrade()`` drops the three tables in FK-safe order
(logs -> assets -> categories).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '040'
down_revision = '039'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if 'asset_categories' not in existing:
        op.create_table(
            'asset_categories',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=False,
                      server_default=sa.text('0')),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name', name='uq_asset_category_name'),
        )

    if 'assets' not in existing:
        op.create_table(
            'assets',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('file_type', sa.String(length=100), nullable=True),
            sa.Column('file_size_bytes', sa.Integer(), nullable=True),
            sa.Column('file_data', sa.Text(), nullable=False),
            sa.Column('thumbnail_data', sa.Text(), nullable=True),
            sa.Column('visibility', sa.String(length=100), nullable=False,
                      server_default=sa.text("'all'")),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('download_count', sa.Integer(), nullable=False,
                      server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['category_id'], ['asset_categories.id'],
                                    ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'],
                                    ondelete='SET NULL'),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_assets_category ON assets (category_id)"
        )

    if 'asset_download_logs' not in existing:
        op.create_table(
            'asset_download_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('downloaded_by', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('downloaded_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['downloaded_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_asset_dl_logs_asset "
            "ON asset_download_logs (asset_id)"
        )


def downgrade() -> None:
    # FK-safe order: logs reference assets; assets reference categories.
    for tbl in ('asset_download_logs', 'assets', 'asset_categories'):
        try:
            op.drop_table(tbl)
        except Exception:
            pass
