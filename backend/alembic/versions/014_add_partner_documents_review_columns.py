"""add rejection_reason and info_request_message columns to partner_documents

Revision ID: 014
Revises: 013
Create Date: 2026-05-17

FPRM-137 — production hotfix. The PartnerDocument model in ``backend/models.py``
gained ``rejection_reason`` (TEXT NULL) and ``info_request_message`` (TEXT NULL)
columns but no Alembic migration was ever generated for them. As a result the
columns exist in the ORM but not in the Railway PostgreSQL database, and any
query that reads ``partner_documents.*`` (e.g. via
``POST /partners/{id}/activation/recalculate`` which counts approved documents)
fails with ``psycopg2.errors.UndefinedColumn``.

This migration restores schema parity:

    - rejection_reason       (TEXT NULL) — populated when an internal reviewer rejects a document
    - info_request_message   (TEXT NULL) — populated when an internal reviewer requests more info

Sprint 9's planned ``deal_messages`` migration moves to revision 015.
"""
from alembic import op
import sqlalchemy as sa


revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'partner_documents',
        sa.Column('rejection_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'partner_documents',
        sa.Column('info_request_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('partner_documents', 'info_request_message')
    op.drop_column('partner_documents', 'rejection_reason')
