"""pipeline toggle on quotes + software/services composition on quote_versions

Revision ID: 032
Revises: 031
Create Date: 2026-05-21

Adds three columns:

* ``quotes.include_in_pipeline`` (Boolean, NOT NULL, default FALSE) --
  channel-manager-controlled flag deciding whether the quote contributes to
  the cross-deal ``pipeline_total`` summary on the internal quotes
  dashboard. Defaults to False so back-filled rows are explicitly opted in
  rather than silently inflating pipeline.
* ``quote_versions.includes_software`` (Boolean, NOT NULL, default TRUE) --
  composition flag indicating the version includes software pricing.
  Existing versions are all software-only, so TRUE is the correct backfill.
* ``quote_versions.includes_services`` (Boolean, NOT NULL, default FALSE) --
  composition flag indicating the version includes services pricing.
  Services pricing is not yet built (see TD: "Implementation services
  pricing quote deferred"); FALSE is the correct backfill for every
  existing version.

Migration 031 was emitted as raw SQL because SQLAlchemy's
``server_default=sa.text('1')`` produced ``DEFAULT 1`` which Postgres
rejects on a BOOLEAN column. The same trap applies here -- so use raw
``DEFAULT TRUE`` / ``DEFAULT FALSE`` via ``op.execute``. ``IF NOT EXISTS``
keeps each statement idempotent so re-running on a partially-applied
database is a no-op.
"""
from alembic import op


revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


_COLUMN_STATEMENTS = [
    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS include_in_pipeline BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE quote_versions ADD COLUMN IF NOT EXISTS includes_software BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE quote_versions ADD COLUMN IF NOT EXISTS includes_services BOOLEAN NOT NULL DEFAULT FALSE",
]

_DROP_STATEMENTS = [
    "ALTER TABLE quote_versions DROP COLUMN IF EXISTS includes_services",
    "ALTER TABLE quote_versions DROP COLUMN IF EXISTS includes_software",
    "ALTER TABLE quotes DROP COLUMN IF EXISTS include_in_pipeline",
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
