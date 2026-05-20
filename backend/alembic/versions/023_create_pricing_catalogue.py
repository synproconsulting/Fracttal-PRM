"""create pricing catalogue: feature_plan_prices, volume_discount_tiers, addon_catalog_items

Revision ID: 023
Revises: 022
Create Date: 2026-05-19

Sprint 15 / FPRM-239 — Phase 5 Quoting module foundation.

Creates three tables and seeds them from the Fracttal Pricing and Quotation
Specification:

- feature_plan_prices       : 3 rows (Starter, Professional, Enterprise)
- volume_discount_tiers     : 6 rows (1-10, 11-50, 51-100, 101-300, 301-500, 500+)
- addon_catalog_items       : 21 rows (per the spec add-on table)

These are read by ``quote_engine.calculate_quote`` (Story 2). Idempotent —
existence checks on every table creation, ``ON CONFLICT DO NOTHING`` on every
seed row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'feature_plan_prices' not in existing:
        op.create_table(
            'feature_plan_prices',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('plan_code', sa.String(), nullable=False),
            sa.Column('feature_pack_annual', sa.Numeric(10, 2), nullable=False),
            sa.Column('transactional_user_annual', sa.Numeric(10, 2), nullable=False),
            sa.Column('limited_tech_user_annual', sa.Numeric(10, 2), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'volume_discount_tiers' not in existing:
        op.create_table(
            'volume_discount_tiers',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('min_users', sa.Integer(), nullable=False),
            sa.Column('max_users', sa.Integer(), nullable=True),
            sa.Column('transactional_user_discount_pct', sa.Numeric(5, 2), nullable=False),
            sa.Column('limited_tech_user_discount_pct', sa.Numeric(5, 2), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'addon_catalog_items' not in existing:
        op.create_table(
            'addon_catalog_items',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('addon_key', sa.String(), nullable=False),
            sa.Column('display_name', sa.String(), nullable=False),
            sa.Column('monthly_price', sa.Numeric(10, 2), nullable=False),
            sa.Column('available_starter', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.Column('available_professional', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.Column('included_enterprise', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.Column('is_active', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('addon_key'),
        )

    # Seed: feature plans
    op.execute("""
        INSERT INTO feature_plan_prices
            (id, plan_code, feature_pack_annual, transactional_user_annual,
             limited_tech_user_annual, is_active, effective_from, created_at)
        SELECT gen_random_uuid(), 'starter',      1161.00, 540.00, 240.00, true, DATE '2024-01-01', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM feature_plan_prices WHERE plan_code = 'starter');

        INSERT INTO feature_plan_prices
            (id, plan_code, feature_pack_annual, transactional_user_annual,
             limited_tech_user_annual, is_active, effective_from, created_at)
        SELECT gen_random_uuid(), 'professional', 2868.00, 720.00, 240.00, true, DATE '2024-01-01', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM feature_plan_prices WHERE plan_code = 'professional');

        INSERT INTO feature_plan_prices
            (id, plan_code, feature_pack_annual, transactional_user_annual,
             limited_tech_user_annual, is_active, effective_from, created_at)
        SELECT gen_random_uuid(), 'enterprise',   8028.00, 900.00, 240.00, true, DATE '2024-01-01', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM feature_plan_prices WHERE plan_code = 'enterprise');
    """)

    # Seed: volume discount tiers
    op.execute("""
        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 1,   10,   0.00,  0.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 1);

        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 11,  50,  30.00, 30.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 11);

        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 51,  100, 40.00, 40.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 51);

        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 101, 300, 50.00, 50.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 101);

        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 301, 500, 60.00, 60.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 301);

        INSERT INTO volume_discount_tiers
            (id, min_users, max_users, transactional_user_discount_pct,
             limited_tech_user_discount_pct, is_active)
        SELECT gen_random_uuid(), 501, NULL, 70.00, 70.00, true
        WHERE NOT EXISTS (SELECT 1 FROM volume_discount_tiers WHERE min_users = 501);
    """)

    # Seed: add-ons (21 rows)
    addon_rows = [
        ('first_tranche_assets',          'First Tranche of Assets',                95.00,  True,  True),
        ('second_tranche_assets',         'Second Tranche of Assets',               55.00,  True,  True),
        ('first_tranche_tasks',           'First Tranche of Tasks',                 95.00,  True,  True),
        ('second_tranche_tasks',          'Second Tranche of Tasks',                55.00,  True,  True),
        ('transaction_log',               'Transaction Log',                        95.00,  True,  False),
        ('virtual_planner',               'Virtual Planner',                        55.00,  True,  True),
        ('trainable_ai_bot',              'Trainable Artificial Intelligence Bot',  95.00,  False, True),
        ('budget',                        'Budget',                                 55.00,  True,  False),
        ('maps',                          'Maps',                                   55.00,  True,  False),
        ('unlimited_request_users',       'Unlimited Request Users',                95.00,  False, True),
        ('unlimited_read_only_users',     'Unlimited Read-only Users',              145.00, False, True),
        ('advanced_warehouse',            'Advanced Warehouse Functionalities',     95.00,  False, True),
        ('guest_portal',                  'Guest Portal',                           95.00,  False, True),
        ('sharing_wo',                    'Sharing WO',                             55.00,  True,  False),
        ('advanced_apis',                 'Advanced APIs',                          145.00, True,  True),
        ('custom_request_portal',         'Custom Request Portal',                  95.00,  False, True),
        ('fracttal_hub',                  'FRACTTAL_HUB',                           55.00,  True,  True),
        ('fracttal_hub_cloud',            'FRACTTAL_HUB_CLOUD',                     55.00,  True,  True),
        ('automator_pro',                 'Automator Pro',                          145.00, True,  False),
        ('fracttal_bi_corp',              'Fracttal BI Corp',                       95.00,  True,  False),
        ('apis',                          'APIs',                                   245.00, False, True),
    ]
    for key, name, price, in_starter, in_pro in addon_rows:
        name_escaped = name.replace("'", "''")
        op.execute(f"""
            INSERT INTO addon_catalog_items
                (id, addon_key, display_name, monthly_price,
                 available_starter, available_professional, included_enterprise, is_active)
            SELECT gen_random_uuid(), '{key}', '{name_escaped}', {price:.2f},
                   {str(in_starter).lower()}, {str(in_pro).lower()}, true, true
            WHERE NOT EXISTS (SELECT 1 FROM addon_catalog_items WHERE addon_key = '{key}');
        """)


def downgrade() -> None:
    op.drop_table('addon_catalog_items')
    op.drop_table('volume_discount_tiers')
    op.drop_table('feature_plan_prices')
