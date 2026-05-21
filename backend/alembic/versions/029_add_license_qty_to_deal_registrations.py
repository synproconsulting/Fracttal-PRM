"""add qty_transactional_users and qty_limited_tech_users to deal_registrations

Revision ID: 029
Revises: 028
Create Date: 2026-05-21

Post-Sprint 20 (Phase 6) deal form fix -- partners now capture the requested
license counts on the deal itself rather than waiting for quote time. The
columns are intentionally nullable: deals registered before this migration,
and deals submitted via the focused internal "+ New Deal" modal, won't have
the values filled in. Quote creation continues to default off these (when
present) via the InternalDealDetail props pass-through.

Idempotent -- skips columns that already exist.
"""
from alembic import op
import sqlalchemy as sa


revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


_NEW_COLUMNS = [
    ('qty_transactional_users', sa.Integer(), True, None),
    ('qty_limited_tech_users',  sa.Integer(), True, None),
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
