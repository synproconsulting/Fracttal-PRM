"""backfill baseline_training_complete for already-activated partners

Revision ID: 018
Revises: 017
Create Date: 2026-05-17

Sprint 9 / FPRM-145 — ``recalculate_activation`` previously hardcoded
``baseline_training_complete=False`` and excluded the flag from the
``activation_complete`` gate. After FPRM-145 the gate REQUIRES the flag.

Without a backfill, the next recalc on any currently-activated partner would
flip them back to ``activation_complete=False``. To preserve their state,
this migration sets ``baseline_training_complete=true`` for every checklist
row where ``activation_complete`` is currently true. Anyone newly active
afterwards must come through ``POST /partners/{id}/activation/training-complete``.
"""
from alembic import op


revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE partner_activation_checklists "
        "SET baseline_training_complete = true "
        "WHERE activation_complete = true"
    )


def downgrade() -> None:
    # Cannot reliably distinguish backfilled rows from genuinely training-complete
    # rows; downgrade is intentionally a no-op.
    pass
