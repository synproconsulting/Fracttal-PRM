"""create approval_step_records table

Revision ID: 026
Revises: 025
Create Date: 2026-05-20

Sprint 17 / FPRM-274 - Multi-step approval enforcement.

Creates ``approval_step_records`` — the audit trail of per-step approve /
reject actions on workflow objects (partner_applications, deal_registrations).
The ``object_id`` column is polymorphic (no FK) since it can reference either
table depending on ``workflow_type``. Indexed by ``object_id`` and by
``(workflow_type, object_id)`` for back-reference reads.

Idempotent — checks for existing table before creating.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'approval_step_records' in inspector.get_table_names():
        return

    op.create_table(
        'approval_step_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_type', sa.String(), nullable=False),
        sa.Column('object_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(), nullable=False),
        sa.Column('required_role', sa.String(), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actioned_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_approval_step_records_object_id',
        'approval_step_records',
        ['object_id'],
    )
    op.create_index(
        'ix_approval_step_records_workflow_object',
        'approval_step_records',
        ['workflow_type', 'object_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_approval_step_records_workflow_object', table_name='approval_step_records')
    op.drop_index('ix_approval_step_records_object_id', table_name='approval_step_records')
    op.drop_table('approval_step_records')
