"""create approval_workflow_steps table + seed default review steps

Revision ID: 021
Revises: 020
Create Date: 2026-05-19

Sprint 13 / FPRM-209 — Phase 4 approval workflow configuration.

Creates the ``approval_workflow_steps`` table and seeds two default rows:

1. partner_application → Channel Ops Review (channel_ops_admin)
2. deal_registration   → Channel Manager Review (channel_manager)

These mirror the currently hardcoded single-reviewer behaviour. Enforcement
of multi-step approval routing is deferred to Phase 5 — this migration only
makes the steps configurable and readable via the program_config endpoints.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'approval_workflow_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_type', sa.String(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(), nullable=False),
        sa.Column('required_role', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_approval_workflow_steps_type_order',
        'approval_workflow_steps',
        ['workflow_type', 'step_order'],
    )

    op.execute("""
        INSERT INTO approval_workflow_steps
            (id, workflow_type, step_order, step_name, required_role, is_active, created_at)
        VALUES
            (gen_random_uuid(), 'partner_application', 1, 'Channel Ops Review', 'channel_ops_admin', true, NOW()),
            (gen_random_uuid(), 'deal_registration',   1, 'Channel Manager Review', 'channel_manager',  true, NOW())
    """)


def downgrade() -> None:
    op.drop_index('ix_approval_workflow_steps_type_order', table_name='approval_workflow_steps')
    op.drop_table('approval_workflow_steps')
