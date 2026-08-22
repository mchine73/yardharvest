"""Record how each lead moved, and which ask each email made.

The CRM held every lead's status *now* and nothing about how it got there, so
the only question that matters — did the leads we emailed in July ever reply,
and which kind of email did it — had no answer anywhere.

* ``crm_lead_status_history`` — one row per transition, with the source that
  caused it (agent / reply / booking / platform / operator / nurture).
  Written only by models.record_lead_status(), which every caller now uses.
* ``crm_agent_action.cta_type`` — signup / book / guide / reply / none, read
  off the body at send time rather than declared by the model, so the label
  cannot drift from the copy.

Revision ID: c3e5a7b9d1f4
Revises: b2d4f6a8c0e2
Create Date: 2026-08-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'c3e5a7b9d1f4'
down_revision = 'b2d4f6a8c0e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_lead_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['crm_contact.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('crm_lead_status_history') as batch:
        batch.create_index('ix_crm_lead_status_history_contact_id', ['contact_id'])
        batch.create_index('ix_crm_lead_status_history_source', ['source'])
        batch.create_index('ix_crm_lead_status_history_changed_at', ['changed_at'])

    with op.batch_alter_table('crm_agent_action') as batch:
        batch.add_column(sa.Column('cta_type', sa.String(length=12), nullable=True))
        batch.create_index('ix_crm_agent_action_cta_type', ['cta_type'])


def downgrade():
    with op.batch_alter_table('crm_agent_action') as batch:
        batch.drop_index('ix_crm_agent_action_cta_type')
        batch.drop_column('cta_type')

    with op.batch_alter_table('crm_lead_status_history') as batch:
        batch.drop_index('ix_crm_lead_status_history_changed_at')
        batch.drop_index('ix_crm_lead_status_history_source')
        batch.drop_index('ix_crm_lead_status_history_contact_id')
    op.drop_table('crm_lead_status_history')
