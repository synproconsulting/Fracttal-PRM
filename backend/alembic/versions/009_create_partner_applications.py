"""create partner_applications and partner_application_documents tables

Revision ID: 009
Revises: 008
Create Date: 2026-05-16

Adds:
    - partner_applications table (public registration drafts + submitted applications)
    - partner_application_documents table (uploaded supporting documents)
    - alters audit_log.actor_id to nullable=True (unauthenticated public events
      such as partner_application.submitted have no User actor)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


APPLICATION_STATUS_VALUES = (
    'draft', 'submitted', 'in_review', 'info_required', 'approved', 'rejected'
)


def upgrade() -> None:
    application_status = postgresql.ENUM(
        *APPLICATION_STATUS_VALUES,
        name='application_status',
        create_type=False,
    )
    application_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'partner_applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('status', application_status, nullable=False, server_default='draft'),
        sa.Column('applicant_email', sa.String(), nullable=False),
        sa.Column('applicant_name', sa.String(), nullable=True),
        sa.Column('applicant_phone', sa.String(), nullable=True),
        sa.Column('applicant_title', sa.String(), nullable=True),
        sa.Column('legal_name', sa.String(), nullable=True),
        sa.Column('dba_name', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('hq_address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('requested_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('territory', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('industries', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('year_established', sa.Integer(), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('annual_revenue', sa.String(), nullable=True),
        sa.Column('shareholders', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('other_software_products', sa.Text(), nullable=True),
        sa.Column('cmms_experience', sa.Boolean(), nullable=True),
        sa.Column('cmms_experience_description', sa.Text(), nullable=True),
        sa.Column('sales_marketing_strategy', sa.Text(), nullable=True),
        sa.Column('technical_support_team', sa.Boolean(), nullable=True),
        sa.Column('technical_support_description', sa.Text(), nullable=True),
        sa.Column('implementation_services', sa.Boolean(), nullable=True),
        sa.Column('implementation_description', sa.Text(), nullable=True),
        sa.Column('partnership_goals', sa.Text(), nullable=True),
        sa.Column('market_growth_plan', sa.Text(), nullable=True),
        sa.Column('additional_info', sa.Text(), nullable=True),
        sa.Column('references', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('terms_accepted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('terms_accepted_at', sa.DateTime(), nullable=True),
        sa.Column('draft_token', sa.String(), nullable=True),
        sa.Column('draft_expires_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('partner_org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('draft_token', name='uq_partner_applications_draft_token'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['partner_org_id'], ['partner_organizations.id']),
    )
    op.create_index('ix_partner_applications_draft_token', 'partner_applications', ['draft_token'])
    op.create_index('ix_partner_applications_status', 'partner_applications', ['status'])

    op.create_table(
        'partner_application_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(), nullable=False),
        sa.Column('document_name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['application_id'], ['partner_applications.id']),
    )
    op.create_index(
        'ix_partner_application_documents_application_id',
        'partner_application_documents',
        ['application_id'],
    )

    op.alter_column('audit_log', 'actor_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.alter_column('audit_log', 'actor_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_index('ix_partner_application_documents_application_id', table_name='partner_application_documents')
    op.drop_table('partner_application_documents')
    op.drop_index('ix_partner_applications_status', table_name='partner_applications')
    op.drop_index('ix_partner_applications_draft_token', table_name='partner_applications')
    op.drop_table('partner_applications')
    application_status = postgresql.ENUM(*APPLICATION_STATUS_VALUES, name='application_status')
    application_status.drop(op.get_bind(), checkfirst=True)
