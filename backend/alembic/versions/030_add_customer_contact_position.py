"""add customer_contact_position to deal_registrations

Revision ID: 030
Revises: 029
Create Date: 2026-05-21

Post-Sprint 20 PR #134 added a customer-side "Contact title" input to the
deal registration form (mapping to ``customer_contact_position``) but the
column was never added to ``deal_registrations`` and the field was never
whitelisted in ``CREATABLE_FIELDS``. Every value the partner typed was
therefore silently discarded by the POST/PATCH handlers, and the read-only
views always rendered "—" for that field.

This migration closes the gap; the router whitelist and the SQLAlchemy
model are updated in the same PR.

Idempotent -- skips if the column already exists.
"""
from alembic import op
import sqlalchemy as sa


revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'deal_registrations' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('deal_registrations')}
    if 'customer_contact_position' in existing:
        return
    op.add_column(
        'deal_registrations',
        sa.Column('customer_contact_position', sa.String(), nullable=True),
    )


def downgrade() -> None:
    try:
        op.drop_column('deal_registrations', 'customer_contact_position')
    except Exception:
        pass
