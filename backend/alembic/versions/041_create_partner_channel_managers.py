"""Sprint 24 PR B / AD-41 -- channel-manager <-> partner assignment

Revision ID: 041
Revises: 040
Create Date: 2026-05-30

Creates ``partner_channel_managers`` -- the many-to-many join that routes
partner-scoped approvals to a partner's assigned channel manager(s). The
unique(partner_org_id, user_id) constraint makes a repeat assignment
idempotent (the API returns 409). No data is seeded -- until the first row
exists, every channel_manager sees all partners (global fallback / bootstrap).

Idempotent: existence-checked create so a partially-applied state replays
cleanly. ``downgrade()`` drops the table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '041'
down_revision = '040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if 'partner_channel_managers' not in existing:
        op.create_table(
            'partner_channel_managers',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
            sa.UniqueConstraint('partner_org_id', 'user_id',
                                name='uq_partner_channel_manager'),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_pcm_user "
            "ON partner_channel_managers (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_pcm_partner "
            "ON partner_channel_managers (partner_org_id)"
        )


def downgrade() -> None:
    try:
        op.drop_table('partner_channel_managers')
    except Exception:
        pass
