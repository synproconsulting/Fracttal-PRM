"""create partner_category_configs and commission_structures tables

Revision ID: 008
Revises: 007
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    commission_type = sa.Enum('autonomous_sell', 'indirect_sell', 'direct_sell', 'co_sell_shared', name='commission_type')
    commission_year = sa.Enum('year_1', 'year_2_plus', name='commission_year')

    op.create_table(
        'partner_category_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deal_reg_sla_hours', sa.Integer(), nullable=False),
        sa.Column('max_discount_pct', sa.Numeric(), nullable=False),
        sa.Column('monthly_fee_usd', sa.Numeric(), nullable=False, server_default='200'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_partner_category_configs_code'), 'partner_category_configs', ['code'], unique=True)

    op.create_table(
        'commission_structures',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_category_code', sa.String(), nullable=False),
        sa.Column('commission_type', commission_type, nullable=False),
        sa.Column('year', commission_year, nullable=False),
        sa.Column('commission_pct', sa.Numeric(), nullable=False),
        sa.Column('subpartner_uplift_pct', sa.Numeric(), nullable=False, server_default='10.0'),
        sa.Column('applies_to_upsell', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['partner_category_code'], ['partner_category_configs.code']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Seed data: 3 categories from Fracttal Distributor Agreement
    op.execute("""
        INSERT INTO partner_category_configs (id, code, display_name, deal_reg_sla_hours, max_discount_pct, monthly_fee_usd, is_active)
        VALUES
          (gen_random_uuid(), 'master', 'Master Partner', 48, 40, 200, true),
          (gen_random_uuid(), 'promotor', 'Promotor Partner', 72, 30, 200, true),
          (gen_random_uuid(), 'reseller', 'Reseller Partner', 96, 20, 200, true)
        ON CONFLICT (code) DO NOTHING;
    """)

    # Seed data: commission structures per category
    for category in ('master', 'promotor', 'reseller'):
        op.execute(f"""
            INSERT INTO commission_structures (id, partner_category_code, commission_type, year, commission_pct, subpartner_uplift_pct, applies_to_upsell)
            VALUES
              (gen_random_uuid(), '{category}', 'autonomous_sell', 'year_1', 50.0, 10.0, true),
              (gen_random_uuid(), '{category}', 'autonomous_sell', 'year_2_plus', 30.0, 0.0, true),
              (gen_random_uuid(), '{category}', 'indirect_sell', 'year_1', 30.0, 10.0, true),
              (gen_random_uuid(), '{category}', 'indirect_sell', 'year_2_plus', 30.0, 0.0, true),
              (gen_random_uuid(), '{category}', 'direct_sell', 'year_1', 10.0, 0.0, true),
              (gen_random_uuid(), '{category}', 'direct_sell', 'year_2_plus', 10.0, 0.0, true),
              (gen_random_uuid(), '{category}', 'co_sell_shared', 'year_1', 25.0, 10.0, true),
              (gen_random_uuid(), '{category}', 'co_sell_shared', 'year_2_plus', 25.0, 0.0, true);
        """)


def downgrade() -> None:
    op.drop_table('commission_structures')
    op.drop_index(op.f('ix_partner_category_configs_code'), table_name='partner_category_configs')
    op.drop_table('partner_category_configs')
    op.execute('DROP TYPE IF EXISTS commission_year')
    op.execute('DROP TYPE IF EXISTS commission_type')
