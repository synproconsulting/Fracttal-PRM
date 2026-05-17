"""create deal_registrations table

Revision ID: 013
Revises: 012
Create Date: 2026-05-17

Sprint 8 / FPRM-125 — deal opportunities registered by partner_admins through
the portal. Status defaults to ``draft``; commission rate is snapshotted from
``commission_structures`` at submission time (Sprint 8 Story 3). Conflict check
fields default to ``not_checked`` and are populated by the Sprint 10 conflict
checker.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'deal_registrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False,
                  server_default=sa.text("'draft'")),

        # Customer info
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('customer_domain', sa.String(), nullable=True),
        sa.Column('customer_contact_name', sa.String(), nullable=True),
        sa.Column('customer_contact_email', sa.String(), nullable=True),
        sa.Column('customer_contact_phone', sa.String(), nullable=True),
        sa.Column('customer_industry', sa.String(), nullable=True),
        sa.Column('customer_country', sa.String(), nullable=True),
        sa.Column('customer_region', sa.String(), nullable=True),

        # Deal info
        sa.Column('deal_name', sa.String(), nullable=False),
        sa.Column('estimated_deal_value', sa.Float(), nullable=True),
        sa.Column('estimated_close_date', sa.Date(), nullable=True),
        sa.Column('deal_notes', sa.Text(), nullable=True),
        sa.Column('commission_type', sa.String(), nullable=True),

        # Commission snapshot
        sa.Column('commission_structure_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('commission_rate_snapshot', sa.Float(), nullable=True),

        # Conflict check
        sa.Column('conflict_checked_at', sa.DateTime(), nullable=True),
        sa.Column('conflict_status', sa.String(), nullable=False,
                  server_default=sa.text("'not_checked'")),
        sa.Column('conflict_notes', sa.Text(), nullable=True),

        # Lifecycle + reviewer
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.ForeignKeyConstraint(['commission_structure_id'], ['commission_structures.id']),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
    )
    op.create_index(
        'ix_deal_registrations_partner_status',
        'deal_registrations',
        ['partner_org_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_deal_registrations_partner_status', table_name='deal_registrations')
    op.drop_table('deal_registrations')
