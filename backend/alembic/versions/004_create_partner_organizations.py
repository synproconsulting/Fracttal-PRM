"""create partner_organizations and partner_profiles tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    program_type = sa.Enum('distributor', 'subpartner', name='program_type')
    partner_category = sa.Enum('master', 'promotor', 'reseller', name='partner_category')
    partner_tier = sa.Enum('registered', 'silver', 'gold', name='partner_tier')
    partner_status = sa.Enum('applicant', 'active', 'suspended', 'inactive', 'terminated', name='partner_status')
    monthly_fee_status = sa.Enum('current', 'overdue', 'waived', name='monthly_fee_status')

    op.create_table(
        'partner_organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('legal_name', sa.String(), nullable=False),
        sa.Column('dba_name', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('hq_address', postgresql.JSONB(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('program_type', program_type, nullable=False),
        sa.Column('partner_category', partner_category, nullable=False),
        sa.Column('parent_partner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tier', partner_tier, nullable=True),
        sa.Column('territory', postgresql.JSONB(), nullable=True),
        sa.Column('industries', postgresql.JSONB(), nullable=True),
        sa.Column('authorized_offerings', postgresql.JSONB(), nullable=True),
        sa.Column('delivery_capabilities', postgresql.JSONB(), nullable=True),
        sa.Column('status', partner_status, nullable=False, server_default='applicant'),
        sa.Column('monthly_fee_status', monthly_fee_status, nullable=False, server_default='current'),
        sa.Column('contract_start_date', sa.Date(), nullable=True),
        sa.Column('contract_end_date', sa.Date(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('certification_expiry_date', sa.Date(), nullable=True),
        sa.Column('hubspot_company_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['parent_partner_id'], ['partner_organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'partner_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('year_established', sa.Integer(), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('annual_revenue', sa.String(), nullable=True),
        sa.Column('shareholders', postgresql.JSONB(), nullable=True),
        sa.Column('cmms_experience', sa.Boolean(), nullable=True),
        sa.Column('cmms_experience_description', sa.Text(), nullable=True),
        sa.Column('other_software_products', sa.Text(), nullable=True),
        sa.Column('sales_marketing_strategy', sa.Text(), nullable=True),
        sa.Column('technical_support_team', sa.Boolean(), nullable=True),
        sa.Column('technical_support_description', sa.Text(), nullable=True),
        sa.Column('implementation_services', sa.Boolean(), nullable=True),
        sa.Column('implementation_description', sa.Text(), nullable=True),
        sa.Column('partnership_goals', sa.Text(), nullable=True),
        sa.Column('market_growth_plan', sa.Text(), nullable=True),
        sa.Column('additional_info', sa.Text(), nullable=True),
        sa.Column('profile_completeness_pct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('partner_org_id'),
    )

    op.create_foreign_key(
        'fk_users_partner_org_id',
        'users', 'partner_organizations',
        ['partner_org_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_partner_org_id', 'users', type_='foreignkey')
    op.drop_table('partner_profiles')
    op.drop_table('partner_organizations')
    op.execute('DROP TYPE IF EXISTS monthly_fee_status')
    op.execute('DROP TYPE IF EXISTS partner_status')
    op.execute('DROP TYPE IF EXISTS partner_tier')
    op.execute('DROP TYPE IF EXISTS partner_category')
    op.execute('DROP TYPE IF EXISTS program_type')
