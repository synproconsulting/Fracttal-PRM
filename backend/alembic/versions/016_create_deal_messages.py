"""create deal_messages table

Revision ID: 016
Revises: 015
Create Date: 2026-05-17

Sprint 9 / FPRM-139 — collaboration thread on deal registrations. Mirrors the
``partner_application_messages`` shape from Sprint 6 (migration 011). Indexed
on (deal_id, created_at) for efficient chronological thread retrieval.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'deal_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_type', sa.String(), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_email', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['deal_id'], ['deal_registrations.id']),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id']),
    )
    op.create_index(
        'ix_deal_messages_deal_created',
        'deal_messages',
        ['deal_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_deal_messages_deal_created', table_name='deal_messages')
    op.drop_table('deal_messages')
