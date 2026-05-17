"""add rejection_reason and info_request_message columns to partner_applications

Revision ID: 010
Revises: 009
Create Date: 2026-05-17

Sprint 6 / FPRM-90 — internal review workflow. Adds two text columns to support
the new approve/reject/request-info endpoints:

    - rejection_reason       (TEXT NULL) — populated on POST /applications/{id}/reject
    - info_request_message   (TEXT NULL) — populated on POST /applications/{id}/request-info

``partner_org_id`` (added in migration 009) is reused by Sprint 6's provisioning
flow (FPRM-92) without a schema change.
"""
from alembic import op
import sqlalchemy as sa


revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'partner_applications',
        sa.Column('rejection_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'partner_applications',
        sa.Column('info_request_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('partner_applications', 'info_request_message')
    op.drop_column('partner_applications', 'rejection_reason')
