"""alter commission_structures.commission_type from PG enum to VARCHAR

Revision ID: 015
Revises: 014
Create Date: 2026-05-17

FPRM-138 — `commission_structures.commission_type` was created in migration
008 as a native PostgreSQL enum (`commission_type` with values
autonomous_sell, indirect_sell, direct_sell, co_sell_shared). The deal
registration form (FPRM-128) writes `deal_registrations.commission_type` as
a plain VARCHAR whose vocabulary is broader by design (see
`deal_registrations_router._snapshot_commission` docstring). When the submit
endpoint filters `CommissionStructure.commission_type == deal.commission_type`
with a value outside the enum (e.g. "reseller"), Postgres raises
`InvalidTextRepresentation` instead of returning zero rows, producing a 500.

This migration converts the column to VARCHAR (existing rows are preserved
because the enum labels are valid text) and drops the now-unused enum type.
The four canonical labels remain valid string values; only the storage type
changes, so `_snapshot_commission` now returns no row instead of crashing for
unknown values, matching the documented best-effort behaviour.
"""
from alembic import op
import sqlalchemy as sa


revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE commission_structures "
        "ALTER COLUMN commission_type TYPE VARCHAR "
        "USING commission_type::text"
    )
    op.execute("DROP TYPE IF EXISTS commission_type")


def downgrade() -> None:
    op.execute(
        "CREATE TYPE commission_type AS ENUM "
        "('autonomous_sell', 'indirect_sell', 'direct_sell', 'co_sell_shared')"
    )
    op.execute(
        "ALTER TABLE commission_structures "
        "ALTER COLUMN commission_type TYPE commission_type "
        "USING commission_type::commission_type"
    )
