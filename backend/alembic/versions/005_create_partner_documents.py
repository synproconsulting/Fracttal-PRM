"""create partner_documents table

Revision ID: 005
Revises: 004
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_type = sa.Enum(
        'id_legal_representative',
        'power_of_attorney',
        'articles_of_incorporation',
        'beneficial_owners_list',
        'fiscal_id',
        'proof_of_fiscal_domicile',
        'bank_certificate',
        'nda',
        'insurance',
        'other',
        name='document_type',
    )
    document_status = sa.Enum(
        'pending_review',
        'approved',
        'rejected',
        'expired',
        name='document_status',
    )

    op.create_table(
        'partner_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', document_type, nullable=False),
        sa.Column('document_name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('status', document_status, nullable=False, server_default='pending_review'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_partner_documents_partner_org_id', 'partner_documents', ['partner_org_id'])


def downgrade() -> None:
    op.drop_index('ix_partner_documents_partner_org_id', table_name='partner_documents')
    op.drop_table('partner_documents')
    op.execute('DROP TYPE IF EXISTS document_status')
    op.execute('DROP TYPE IF EXISTS document_type')
