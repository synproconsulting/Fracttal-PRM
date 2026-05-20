"""create quote schema: quotes, quote_versions, quote_line_items

Revision ID: 024
Revises: 023
Create Date: 2026-05-19

Sprint 15 / FPRM-239 — Phase 5 Quoting module data model.

- quotes              : Quote header bound to a deal_registrations row.
- quote_versions      : Versioned pricing snapshots; multiple per quote;
                        supports Good/Better/Best scenarios via scenario_label.
- quote_line_items    : Individual line items computed by quote_engine.

Idempotent — existence checks on every table creation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'quotes' not in existing:
        op.create_table(
            'quotes',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('quote_name', sa.String(), nullable=True),
            sa.Column('currency_code', sa.String(length=3), nullable=False,
                      server_default=sa.text("'USD'")),
            sa.Column('active_version', sa.Integer(), nullable=False,
                      server_default=sa.text('1')),
            sa.Column('active_scenario', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False,
                      server_default=sa.text("'draft'")),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['deal_id'], ['deal_registrations.id']),
            sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        )
        op.create_index('ix_quotes_deal_id', 'quotes', ['deal_id'])

    if 'quote_versions' not in existing:
        op.create_table(
            'quote_versions',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('scenario_label', sa.String(), nullable=True),
            sa.Column('feature_plan', sa.String(), nullable=False),
            sa.Column('feature_plan_discount_pct', sa.Numeric(5, 2), nullable=False,
                      server_default=sa.text('0')),
            sa.Column('qty_transactional_users', sa.Integer(), nullable=False),
            sa.Column('qty_limited_tech_users', sa.Integer(), nullable=False),
            sa.Column('selected_addons', postgresql.JSONB(astext_type=sa.Text()),
                      nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column('grand_total_before_discount', sa.Numeric(12, 2), nullable=False),
            sa.Column('grand_total_after_discount', sa.Numeric(12, 2), nullable=False),
            sa.Column('pdf_artifact_path', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('is_deleted', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('quote_id', 'version_number',
                                name='uq_quote_versions_quote_version'),
            sa.ForeignKeyConstraint(['quote_id'], ['quotes.id']),
        )
        op.create_index('ix_quote_versions_quote_id', 'quote_versions', ['quote_id'])

    if 'quote_line_items' not in existing:
        op.create_table(
            'quote_line_items',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('quote_version_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('line_order', sa.Integer(), nullable=False),
            sa.Column('line_type', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('unit_price', sa.Numeric(10, 2), nullable=False),
            sa.Column('discount_pct', sa.Numeric(5, 2), nullable=False,
                      server_default=sa.text('0')),
            sa.Column('total_before_discount', sa.Numeric(12, 2), nullable=False),
            sa.Column('total_after_discount', sa.Numeric(12, 2), nullable=False),
            sa.Column('addon_key', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['quote_version_id'], ['quote_versions.id']),
        )
        op.create_index('ix_quote_line_items_version_id', 'quote_line_items',
                        ['quote_version_id'])


def downgrade() -> None:
    op.drop_table('quote_line_items')
    op.drop_table('quote_versions')
    op.drop_table('quotes')
