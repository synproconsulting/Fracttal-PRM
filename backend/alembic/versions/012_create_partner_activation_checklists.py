"""create partner_activation_checklists table

Revision ID: 012
Revises: 011
Create Date: 2026-05-17

Sprint 7 / FPRM-107 / AD-14 — gates partner self-service features (deal
registration, etc) on completion of profile + documents + signed agreement.
Provisioning creates an all-False row; ``recalculate_activation`` flips flags
as evidence arrives.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'partner_activation_checklists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('profile_complete', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('documents_uploaded', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('terms_signed', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('baseline_training_complete', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('activation_complete', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.UniqueConstraint('partner_org_id', name='uq_partner_activation_checklists_partner_org_id'),
    )


def downgrade() -> None:
    op.drop_table('partner_activation_checklists')
