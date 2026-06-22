"""CRM BDR lead lifecycle + agent-action approval queue

Adds the lead-working lifecycle to crm_contact (status / owner / source /
last-contacted / next-action) that a BDR (and the AI BDR agent) works a contact
through, and a crm_agent_action table holding agent-proposed next steps for
human approval ('man in the middle').

Revision ID: c5e7a9b1d3f5
Revises: f1a3c5e7b9d2
Create Date: 2026-06-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'c5e7a9b1d3f5'
down_revision = 'f1a3c5e7b9d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as b:
        b.add_column(sa.Column('lead_status', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('source', sa.String(length=60), nullable=True))
        b.add_column(sa.Column('last_contacted_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('next_action_at', sa.Date(), nullable=True))
        b.add_column(sa.Column('next_action_note', sa.String(length=200), nullable=True))
        b.create_index('ix_crm_contact_lead_status', ['lead_status'])
        b.create_index('ix_crm_contact_next_action_at', ['next_action_at'])
        b.create_foreign_key('fk_crm_contact_owner_id', 'crm_user', ['owner_id'], ['id'])

    # Backfill existing contacts to the entry state.
    op.execute("UPDATE crm_contact SET lead_status='New' WHERE lead_status IS NULL")

    op.create_table(
        'crm_agent_action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('deal_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('result', sa.String(length=400), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['crm_contact.id']),
        sa.ForeignKeyConstraint(['company_id'], ['crm_company.id']),
        sa.ForeignKeyConstraint(['deal_id'], ['crm_deal.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['crm_user.id']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['crm_user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_crm_agent_action_status', 'crm_agent_action', ['status'])


def downgrade():
    op.drop_index('ix_crm_agent_action_status', table_name='crm_agent_action')
    op.drop_table('crm_agent_action')
    with op.batch_alter_table('crm_contact') as b:
        b.drop_constraint('fk_crm_contact_owner_id', type_='foreignkey')
        b.drop_index('ix_crm_contact_next_action_at')
        b.drop_index('ix_crm_contact_lead_status')
        b.drop_column('next_action_note')
        b.drop_column('next_action_at')
        b.drop_column('last_contacted_at')
        b.drop_column('source')
        b.drop_column('owner_id')
        b.drop_column('lead_status')
