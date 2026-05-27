"""Sprint 22 -- document_type_rules table + seed defaults

Revision ID: 038
Revises: 037
Create Date: 2026-05-27

Creates the admin-maintainable approval-workflow rules table that decides
whether a document type auto-approves on upload or requires manual review.

Two seed rows codify the corrected Sprint 21 hotfix (FPRM-353) behaviour:

* ``quote_acceptance`` -- ``auto_approve = true``, ``requires_approval =
  false``. Channel managers attaching signed order forms shouldn't have
  to re-approve their own evidence; the attachment itself is the
  affirmative act.
* ``contract`` -- ``requires_approval = true``, ``auto_approve = false``.
  Partner contracts genuinely need a second pair of eyes.

Idempotent: existence check on the table name; the seed inserts use
``ON CONFLICT DO NOTHING`` (Postgres) so a re-run after the initial seed
is a no-op.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'document_type_rules' not in set(inspector.get_table_names()):
        op.create_table(
            'document_type_rules',
            sa.Column(
                'id',
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text('gen_random_uuid()'),
            ),
            sa.Column('document_type', sa.String(length=100), nullable=False),
            sa.Column(
                'requires_approval',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('true'),
            ),
            sa.Column(
                'auto_approve',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'),
            ),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column(
                'created_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('NOW()'),
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('NOW()'),
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('document_type', name='uq_doc_type_rule'),
        )

    if bind.dialect.name == 'postgresql':
        op.execute(
            """
            INSERT INTO document_type_rules
                (document_type, requires_approval, auto_approve, description)
            VALUES
              ('quote_acceptance', false, true,
               'Quote acceptance -- attachment is sufficient evidence; no manual approval required'),
              ('contract', true, false,
               'Partner contracts -- require manual approval by channel manager or system admin')
            ON CONFLICT (document_type) DO NOTHING
            """
        )
    else:
        for doc_type, requires_approval, auto_approve, desc in (
            (
                'quote_acceptance',
                False,
                True,
                'Quote acceptance -- attachment is sufficient evidence; no manual approval required',
            ),
            (
                'contract',
                True,
                False,
                'Partner contracts -- require manual approval by channel manager or system admin',
            ),
        ):
            op.execute(
                sa.text(
                    "INSERT INTO document_type_rules "
                    "(id, document_type, requires_approval, auto_approve, description) "
                    "SELECT lower(hex(randomblob(16))), :dt, :ra, :aa, :d "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM document_type_rules WHERE document_type = :dt"
                    ")"
                ).bindparams(dt=doc_type, ra=requires_approval, aa=auto_approve, d=desc)
            )


def downgrade() -> None:
    try:
        op.drop_table('document_type_rules')
    except Exception:
        pass
