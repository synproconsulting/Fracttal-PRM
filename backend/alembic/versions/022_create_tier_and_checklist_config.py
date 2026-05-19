"""create partner_tiers, partner_tier_eligibility_rules, activation_checklist_config

Revision ID: 022
Revises: 021
Create Date: 2026-05-19

Sprint 13 / FPRM-213 — Phase 4 partner tier + activation checklist configuration.

Creates three tables and seeds them with defaults that match the currently
hardcoded behaviour in ``activation.py``:

- ``partner_tiers`` — 3 rows: Registered (rank 1), Silver (rank 2), Gold (rank 3).
- ``partner_tier_eligibility_rules`` — empty by default (admins add rules).
- ``activation_checklist_config`` — 6 rows mirroring the four mandatory flags
  used by ``recalculate_activation`` plus two optional placeholders for the
  Phase 5 dynamic-enforcement work (``contract_signed``, ``training_advanced_complete``).

Dynamic enforcement that reads from these tables is deferred to Phase 5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'partner_tiers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tier_name', sa.String(), nullable=False),
        sa.Column('tier_rank', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tier_name'),
    )

    op.create_table(
        'partner_tier_eligibility_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('rule_value', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tier_id'], ['partner_tiers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_tier_rules_tier_id', 'partner_tier_eligibility_rules', ['tier_id'])

    op.create_table(
        'activation_checklist_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('partner_category_code', sa.String(), nullable=True),
        sa.Column('tier_name', sa.String(), nullable=True),
        sa.Column('criterion_key', sa.String(), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Seed: 3 default tiers
    op.execute("""
        INSERT INTO partner_tiers (id, tier_name, tier_rank, description, is_active, created_at)
        VALUES
            (gen_random_uuid(), 'Registered', 1, 'Entry-level partner tier', true, NOW()),
            (gen_random_uuid(), 'Silver',     2, 'Established partner with proven track record', true, NOW()),
            (gen_random_uuid(), 'Gold',       3, 'Top-tier partner with highest performance', true, NOW())
    """)

    # Seed: default activation criteria matching the current hardcoded gates
    op.execute("""
        INSERT INTO activation_checklist_config
            (id, partner_category_code, tier_name, criterion_key, is_required, description, is_active)
        VALUES
            (gen_random_uuid(), NULL, NULL, 'profile_complete',            true,  'Partner profile must be fully completed', true),
            (gen_random_uuid(), NULL, NULL, 'documents_uploaded',          true,  'Required documents must be uploaded and approved', true),
            (gen_random_uuid(), NULL, NULL, 'baseline_training_complete',  true,  'Baseline training must be completed', true),
            (gen_random_uuid(), NULL, NULL, 'terms_signed',                true,  'Partnership terms must be signed (contract_start_date set)', true),
            (gen_random_uuid(), NULL, NULL, 'contract_signed',             false, 'Formal contract signed (optional by default)', true),
            (gen_random_uuid(), NULL, NULL, 'training_advanced_complete',  false, 'Advanced training (optional by default)', true)
    """)


def downgrade() -> None:
    op.drop_table('activation_checklist_config')
    op.drop_index('ix_tier_rules_tier_id', table_name='partner_tier_eligibility_rules')
    op.drop_table('partner_tier_eligibility_rules')
    op.drop_table('partner_tiers')
