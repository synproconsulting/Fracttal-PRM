"""create partner_activities table

Revision ID: 007
Revises: 006
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    activity_type = sa.Enum('note', 'task', 'call', 'meeting', 'email', 'status_change', name='activity_type')

    op.create_table(
        'partner_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('activity_type', activity_type, nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_to_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_partner_activities_partner_org_id', 'partner_activities', ['partner_org_id'])


def downgrade() -> None:
    op.drop_index('ix_partner_activities_partner_org_id', table_name='partner_activities')
    op.drop_table('partner_activities')
    op.execute('DROP TYPE IF EXISTS activity_type')
