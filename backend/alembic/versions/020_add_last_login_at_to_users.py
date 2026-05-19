"""add last_login_at to users

Revision ID: 020
Revises: 019
Create Date: 2026-05-19

Sprint 12 / FPRM-194 — captures the most recent successful login per user so
the internal user management UI can show admins who has and hasn't engaged
with the platform. Populated by the ``POST /auth/login`` happy path.
"""
from alembic import op
import sqlalchemy as sa


revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_login_at')
