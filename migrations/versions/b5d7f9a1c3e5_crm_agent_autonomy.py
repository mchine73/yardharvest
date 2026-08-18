"""BDR agent autonomy: settings singleton, inbound replies, auto_executed flag

- crm_agent_settings: operator policy for the autonomous cycle (master
  switch, per-action flags, send cap/window, breakers) plus the durable
  claim/lease state the cron tick and reply poller use to stay idempotent
  across processes.
- crm_inbound_reply: replies captured from the operator's mailbox by the
  IMAP poller — the feedback signal that stops the follow-up cadence.
- crm_agent_action.auto_executed: stamped when the cycle executed a
  proposal without a human click; plus a (contact_id, status) index for
  the "any pending proposal for this contact" checks the cycle does per
  lead.

Revision ID: b5d7f9a1c3e5
Revises: a4c6e8b0d2f4
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op

revision = 'b5d7f9a1c3e5'
down_revision = 'a4c6e8b0d2f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_agent_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('autonomy_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('paused_reason', sa.String(length=300), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('daily_send_cap', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('weekdays_only', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('send_hour_local', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('timezone', sa.String(length=64), nullable=False,
                  server_default='America/Chicago'),
        sa.Column('digest_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('digest_email', sa.String(length=255), nullable=True),
        sa.Column('notify_on_interested', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('operator_user_id', sa.Integer(), sa.ForeignKey('crm_user.id'), nullable=True),
        sa.Column('auto_followups', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('auto_promote_cold', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('auto_new_leads', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_enrich', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_replies', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_campaigns', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_facebook', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('require_reply_capture', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('max_consecutive_send_failures', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_hard_bounces_24h', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_cycle_date', sa.Date(), nullable=True),
        sa.Column('last_cycle_started_at', sa.DateTime(), nullable=True),
        sa.Column('last_cycle_finished_at', sa.DateTime(), nullable=True),
        sa.Column('cycle_lock_until', sa.DateTime(), nullable=True),
        sa.Column('last_cycle_summary_json', sa.Text(), nullable=True),
        sa.Column('poll_lock_until', sa.DateTime(), nullable=True),
        sa.Column('last_reply_poll_at', sa.DateTime(), nullable=True),
        sa.Column('last_reply_poll_ok_at', sa.DateTime(), nullable=True),
        sa.Column('imap_last_error', sa.String(length=400), nullable=True),
        sa.Column('imap_uidvalidity', sa.Integer(), nullable=True),
        sa.Column('imap_last_uid', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'crm_inbound_reply',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('crm_contact.id'), nullable=True),
        sa.Column('from_email', sa.String(length=255), nullable=True),
        sa.Column('from_name', sa.String(length=160), nullable=True),
        sa.Column('subject', sa.String(length=300), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('message_id', sa.String(length=255), nullable=True),
        sa.Column('in_reply_to', sa.String(length=255), nullable=True),
        sa.Column('imap_uidvalidity', sa.Integer(), nullable=True),
        sa.Column('imap_uid', sa.Integer(), nullable=True),
        sa.Column('classification', sa.String(length=20), nullable=True),
        sa.Column('summary', sa.String(length=300), nullable=True),
        sa.Column('action_taken', sa.String(length=300), nullable=True),
        sa.Column('agent_action_id', sa.Integer(), sa.ForeignKey('crm_agent_action.id'),
                  nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('message_id', name='uq_crm_inbound_reply_message_id'),
    )
    op.create_index('ix_crm_inbound_reply_contact_id', 'crm_inbound_reply', ['contact_id'])
    op.create_index('ix_crm_inbound_reply_from_email', 'crm_inbound_reply', ['from_email'])
    op.create_index('ix_crm_inbound_reply_classification', 'crm_inbound_reply', ['classification'])
    op.create_index('ix_crm_inbound_reply_created_at', 'crm_inbound_reply', ['created_at'])

    with op.batch_alter_table('crm_agent_action') as b:
        b.add_column(sa.Column('auto_executed', sa.Boolean(), nullable=False,
                               server_default=sa.false()))
        b.create_index('ix_crm_agent_action_contact_status', ['contact_id', 'status'])


def downgrade():
    with op.batch_alter_table('crm_agent_action') as b:
        b.drop_index('ix_crm_agent_action_contact_status')
        b.drop_column('auto_executed')
    op.drop_index('ix_crm_inbound_reply_created_at', table_name='crm_inbound_reply')
    op.drop_index('ix_crm_inbound_reply_classification', table_name='crm_inbound_reply')
    op.drop_index('ix_crm_inbound_reply_from_email', table_name='crm_inbound_reply')
    op.drop_index('ix_crm_inbound_reply_contact_id', table_name='crm_inbound_reply')
    op.drop_table('crm_inbound_reply')
    op.drop_table('crm_agent_settings')
