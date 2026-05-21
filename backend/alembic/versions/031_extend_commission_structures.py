"""extend commission_structures with is_active and timestamps

Revision ID: 031
Revises: 030
Create Date: 2026-05-21

Adds the columns the new ``/internal/config/commission-rates`` admin UI
needs:

* ``is_active`` (Boolean, NOT NULL, default True) -- soft-delete flag.
  ``DELETE /internal/config/commission-rates/{id}`` flips this to False
  rather than dropping the row, so historical deal commission snapshots
  keep a valid ``commission_structure_id`` FK target.
* ``created_at`` / ``updated_at`` (DateTime, NOT NULL) -- standard audit
  timestamps; required by the admin table's "Show inactive" toggle and
  by future per-row history surfaces.

Existing rows seeded by migrations 014/015 backfill to
``is_active = True`` and ``created_at = NOW()`` so legacy
``_snapshot_commission`` lookups in deal submission continue to resolve.

Idempotent -- skips any column that already exists.
"""
from alembic import op
import sqlalchemy as sa


revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


_NEW_COLUMNS = [
    ('is_active',  sa.Boolean(),  False, sa.text('1')),
    ('created_at', sa.DateTime(), False, sa.text('CURRENT_TIMESTAMP')),
    ('updated_at', sa.DateTime(), False, sa.text('CURRENT_TIMESTAMP')),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'commission_structures' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('commission_structures')}
    for name, type_, nullable, server_default in _NEW_COLUMNS:
        if name in existing:
            continue
        kwargs = {'nullable': nullable}
        if server_default is not None:
            kwargs['server_default'] = server_default
        op.add_column('commission_structures', sa.Column(name, type_, **kwargs))


def downgrade() -> None:
    for name, *_ in _NEW_COLUMNS:
        try:
            op.drop_column('commission_structures', name)
        except Exception:
            pass
