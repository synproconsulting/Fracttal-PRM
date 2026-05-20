"""add category and sort_order to addon_catalog_items

Revision ID: 028
Revises: 027
Create Date: 2026-05-20

Sprint 20 / FPRM-318 (Phase 6) -- the add-on catalogue now has 68 items
(21 seeded + 47 added live via the pricing admin API). Without categories
and sort order, both the Pricing admin tab and the quote-form add-on
selector are unwieldy lists. This migration adds the two columns; the
taxonomy itself is admin-maintainable data per AD-25 and is populated
post-deploy via ``PATCH /internal/config/pricing/addons/{id}`` -- never
in a migration.

``sort_order`` is NOT NULL with ``server_default='0'`` so the backfill on
existing rows succeeds without app intervention. ``category`` is left
nullable so existing rows fall into the quote-form's "Other" group until
they're assigned one.

Idempotent -- skips columns that already exist.
"""
from alembic import op
import sqlalchemy as sa


revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


_NEW_COLUMNS = [
    ('category',   sa.String(),  True,  None),
    ('sort_order', sa.Integer(), False, sa.text("'0'")),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'addon_catalog_items' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('addon_catalog_items')}
    for name, type_, nullable, server_default in _NEW_COLUMNS:
        if name in existing:
            continue
        kwargs = {'nullable': nullable}
        if server_default is not None:
            kwargs['server_default'] = server_default
        op.add_column('addon_catalog_items', sa.Column(name, type_, **kwargs))


def downgrade() -> None:
    for name, *_ in _NEW_COLUMNS:
        try:
            op.drop_column('addon_catalog_items', name)
        except Exception:
            pass
