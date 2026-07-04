"""Email delivery event log

One row per ZeptoMail webhook event (hard/soft bounce, complaint, open,
click) — history for the CRM deliverability dashboard. Contact columns only
hold the latest bounce state; this keeps the trail.

Revision ID: d5f7a9b1c3e4
Revises: c4e6f8a0b2d3
Create Date: 2026-07-03
"""
import sqlalchemy as sa
from alembic import op

revision = 'd5f7a9b1c3e4'
down_revision = 'c4e6f8a0b2d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_email_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('event_type', sa.String(length=12), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_crm_email_event_email', 'crm_email_event', ['email'])
    op.create_index('ix_crm_email_event_event_type', 'crm_email_event', ['event_type'])
    op.create_index('ix_crm_email_event_contact_id', 'crm_email_event', ['contact_id'])
    op.create_index('ix_crm_email_event_created_at', 'crm_email_event', ['created_at'])


def downgrade():
    op.drop_index('ix_crm_email_event_created_at', table_name='crm_email_event')
    op.drop_index('ix_crm_email_event_contact_id', table_name='crm_email_event')
    op.drop_index('ix_crm_email_event_event_type', table_name='crm_email_event')
    op.drop_index('ix_crm_email_event_email', table_name='crm_email_event')
    op.drop_table('crm_email_event')
