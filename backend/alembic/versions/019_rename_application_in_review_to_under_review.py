"""rename application_status enum value in_review -> under_review

Revision ID: 019
Revises: 018
Create Date: 2026-05-19

Sprint 12 / FPRM-191 + FPRM-192 — aligns the application_status enum with
deal status terminology. Applications previously transitioned to ``in_review``
on internal pickup; deals use ``under_review`` for the same state. The
mismatch caused ``GET /applications?status=under_review`` to 500 and made
the status filters inconsistent across the UI.

PostgreSQL supports ``ALTER TYPE ... RENAME VALUE`` since v10, so existing
rows carry over automatically. The migration is a no-op on SQLite (tests
rebuild the schema from ``Base.metadata.create_all()`` which already reflects
the renamed enum).
"""
from alembic import op


revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TYPE application_status RENAME VALUE 'in_review' TO 'under_review'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TYPE application_status RENAME VALUE 'under_review' TO 'in_review'"
        )
