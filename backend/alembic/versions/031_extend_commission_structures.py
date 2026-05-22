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
* ``created_at`` / ``updated_at`` (DateTime, NOT NULL, default
  CURRENT_TIMESTAMP) -- standard audit timestamps. Existing rows seeded
  by migrations 014/015 backfill with the current timestamp so they
  satisfy the model's ``nullable=False`` declaration immediately.

Idempotent -- the ``IF NOT EXISTS`` guards make re-running this
migration on a partially-applied database a no-op.
"""
from alembic import op


revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


# Raw SQL via ``op.execute`` rather than ``op.add_column`` + ``sa.Column``.
#
# The original PR #142 migration used
# ``server_default=sa.text('1')`` for the is_active boolean, which
# SQLAlchemy emits as ``DEFAULT 1`` -- valid on SQLite but rejected by
# Postgres with::
#
#     DatatypeMismatch: column "is_active" is of type boolean
#     but default expression is of type integer
#
# Two follow-up attempts (``sa.true()``, then a model-only adjustment)
# kept emitting the integer literal too. Inlining ``DEFAULT TRUE`` as
# raw SQL takes SQLAlchemy's type translation out of the picture
# entirely; Postgres sees exactly the boolean default it expects.
# ``IF NOT EXISTS`` (Postgres 9.6+) keeps each statement idempotent.
_COLUMN_STATEMENTS = [
    "ALTER TABLE commission_structures ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE commission_structures ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE commission_structures ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
]

_DROP_STATEMENTS = [
    "ALTER TABLE commission_structures DROP COLUMN IF EXISTS updated_at",
    "ALTER TABLE commission_structures DROP COLUMN IF EXISTS created_at",
    "ALTER TABLE commission_structures DROP COLUMN IF EXISTS is_active",
]


def upgrade() -> None:
    for stmt in _COLUMN_STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DROP_STATEMENTS:
        try:
            op.execute(stmt)
        except Exception:
            pass
