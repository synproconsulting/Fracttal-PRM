"""extend deal_registrations with Section A + Section B SPICED fields and created_on_behalf_of

Revision ID: 027
Revises: 026
Create Date: 2026-05-20

Sprint 20 / FPRM-315 + FPRM-317 (Phase 6) -- extends ``deal_registrations``
with the full DEAL INFORMATION form per the Fracttal Pricing and Quotation
Specification: Section A additional prospect/engagement fields, Section B
Current State (Situation) + Feature Requirements + SPICED narratives, plus
``created_on_behalf_of`` (Story FPRM-317) so the same migration captures all
Sprint 20 deal-table changes.

Idempotent: skips columns that already exist (safe to re-run).
"""
from alembic import op
import sqlalchemy as sa


revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


# (name, type, nullable, server_default)
_NEW_COLUMNS = [
    # Section A -- additional prospect/engagement fields
    ('engagement_date',           sa.Date(),    True,  None),
    ('prospect_phone',            sa.String(),  True,  None),
    ('compiled_by',               sa.String(),  True,  None),
    ('prospect_contact_name',     sa.String(),  True,  None),
    ('prospect_contact_position', sa.String(),  True,  None),
    ('prospect_website',          sa.String(),  True,  None),
    ('industry_sector',           sa.String(),  True,  None),
    ('company_size',              sa.String(),  True,  None),
    ('feature_plan_preference',   sa.String(),  True,  None),

    # Section B -- Current State (Situation): what they have today
    ('current_system',     sa.String(), True, None),
    ('old_system',         sa.String(), True, None),
    ('inventory_stores',   sa.String(), True, None),
    ('work_orders_prs',    sa.String(), True, None),
    ('monitoring_system',  sa.String(), True, None),

    # Section B -- Feature requirements (Yes/No + free-text companions)
    ('need_asset_depreciation',    sa.Boolean(), True, None),
    ('need_wo_wr',                 sa.Boolean(), True, None),
    ('need_reports',               sa.Boolean(), True, None),
    ('need_tool_management',       sa.Boolean(), True, None),
    ('need_purchasing',            sa.Boolean(), True, None),
    ('need_integration',           sa.Boolean(), True, None),
    ('integration_with',           sa.String(),  True, None),
    ('need_multi_language',        sa.Boolean(), True, None),
    ('languages_required',         sa.String(),  True, None),
    ('need_asset_management',      sa.Boolean(), True, None),
    ('need_document_management',   sa.Boolean(), True, None),
    ('need_cost_tracking',         sa.Boolean(), True, None),
    ('need_monitoring',            sa.Boolean(), True, None),
    ('need_schedule_third_parties', sa.Boolean(), True, None),
    ('need_track_labour',          sa.Boolean(), True, None),

    # Section B -- SPICED narrative fields
    ('about_client',    sa.Text(), True, None),
    ('pain',            sa.Text(), True, None),
    ('impact',          sa.Text(), True, None),
    ('critical_event',  sa.Text(), True, None),
    ('decision',        sa.Text(), True, None),
    ('next_steps',      sa.Text(), True, None),

    # FPRM-317 -- True when an internal user (channel_manager+) created the
    # deal on behalf of a partner. NOT NULL with server_default=false so the
    # backfill on existing rows succeeds in Postgres without app intervention.
    ('created_on_behalf_of', sa.Boolean(), False, sa.text('false')),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'deal_registrations' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('deal_registrations')}
    for name, type_, nullable, server_default in _NEW_COLUMNS:
        if name in existing:
            continue
        kwargs = {'nullable': nullable}
        if server_default is not None:
            kwargs['server_default'] = server_default
        op.add_column('deal_registrations', sa.Column(name, type_, **kwargs))


def downgrade() -> None:
    for name, *_ in _NEW_COLUMNS:
        try:
            op.drop_column('deal_registrations', name)
        except Exception:
            pass
