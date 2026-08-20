"""Type the organizations that can pay, and stop re-enriching dead ones.

The CRM could not tell a multi-garden operator from a 20-plot volunteer
garden: the importer flattened 'nonprofit' into 'Independent', contact titles
were asked for and thrown away, and nothing recorded that enrichment had
already looked at a company — so the batch chewed the same first fifteen rows
on every run and never reached the tail.

* ``crm_contact.title`` — the job title scouting and enrichment already found.
  "Executive Director" is what says whether this person can decide anything.
* ``crm_company.sites_count`` — how many gardens they run. More than one means
  an operator: seats, a budget, and one conversation covering many gardens.
* ``crm_company.enrich_attempted_at`` — when we last looked, found or not.
* ``crm_agent_settings.operator_weight`` — how much the ICP score favours the
  types with a budget line. 2.0 is the GTM thesis, and a setting so it can be
  lowered the moment reply rates disagree with it.

No data is rewritten here. Re-typing the ~400 existing organizations is a
separate, inspectable step: ``flask crm backfill-org-types --dry-run``.

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5b7d9f2
Create Date: 2026-08-19
"""
import sqlalchemy as sa
from alembic import op

revision = 'b2d4f6a8c0e2'
down_revision = 'a1c3e5b7d9f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as batch:
        batch.add_column(sa.Column('title', sa.String(length=120), nullable=True))

    with op.batch_alter_table('crm_company') as batch:
        batch.add_column(sa.Column('sites_count', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('enrich_attempted_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('crm_agent_settings') as batch:
        batch.add_column(sa.Column('operator_weight', sa.Float(), nullable=False,
                                   server_default='2.0'))


def downgrade():
    with op.batch_alter_table('crm_agent_settings') as batch:
        batch.drop_column('operator_weight')

    with op.batch_alter_table('crm_company') as batch:
        batch.drop_column('enrich_attempted_at')
        batch.drop_column('sites_count')

    with op.batch_alter_table('crm_contact') as batch:
        batch.drop_column('title')
