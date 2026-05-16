"""create partner_user_invites table

Revision ID: 006
Revises: 005
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    invited_role = sa.Enum('partner_user', 'partner_admin', name='invited_role')

    op.create_table(
        'partner_user_invites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('invited_role', invited_role, nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_partner_user_invites_token'), 'partner_user_invites', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_partner_user_invites_token'), table_name='partner_user_invites')
    op.drop_table('partner_user_invites')
    op.execute('DROP TYPE IF EXISTS invited_role')
