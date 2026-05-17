"""create partner_application_messages table

Revision ID: 011
Revises: 010
Create Date: 2026-05-17

Sprint 6 / FPRM-91 — applicant info-required response flow. Stores the message
thread between applicants (replying via draft_token) and internal reviewers
(authenticated). One row per message.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'partner_application_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_type', sa.String(), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_email', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['partner_applications.id']),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id']),
    )
    op.create_index(
        'ix_partner_application_messages_application_id',
        'partner_application_messages',
        ['application_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_partner_application_messages_application_id',
        table_name='partner_application_messages',
    )
    op.drop_table('partner_application_messages')
