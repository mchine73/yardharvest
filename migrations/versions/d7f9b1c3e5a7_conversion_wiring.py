"""Wire the CRM to the product: platform status, trial-drip catch-up, caps.

The CRM could not see a sale. Nothing linked a crm_contact to a User /
CommunityGarden / GardenSubscription, so "did this lead ever sign up, trial, or
pay?" was unanswerable and 'Customer' was only ever set by hand. This adds the
columns that make the funnel measurable end to end:

* ``crm_contact.platform_status`` / ``platform_status_at`` — written by the
  nightly reconciliation (autonomy.reconcile_platform_status), and the reason
  cold outreach can now skip anyone who already has a garden.
* ``crm_contact.nurture_cycles`` — caps recycling a silent lead at two 90-day
  rounds instead of forever.
* ``crm_agent_settings.daily_ai_budget_usd`` — a ledger-based spend stop.
* ``crm_agent_settings.last_match_*`` — so the digest can report the match RATE
  honestly rather than implying full coverage.
* ``garden_subscription.last_drip_day`` — the trial drip now records the
  highest step it has sent, so a missed heartbeat day catches up instead of
  skipping that email forever.
* ``community_garden.trial_nudge_sent_at`` — send-once marker for the day-2
  "start your free trial" nudge.

Revision ID: d7f9b1c3e5a7
Revises: c6e8a0b2d4f6
Create Date: 2026-08-18
"""
import sqlalchemy as sa
from alembic import op

revision = 'd7f9b1c3e5a7'
down_revision = 'c6e8a0b2d4f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as batch:
        batch.add_column(sa.Column('platform_status', sa.String(length=20),
                                   nullable=True))
        batch.add_column(sa.Column('platform_status_at', sa.DateTime(),
                                   nullable=True))
        batch.add_column(sa.Column('nurture_cycles', sa.Integer(),
                                   nullable=False, server_default='0'))
        batch.create_index('ix_crm_contact_platform_status', ['platform_status'])

    with op.batch_alter_table('crm_agent_settings') as batch:
        batch.add_column(sa.Column('daily_ai_budget_usd', sa.Numeric(8, 2),
                                   nullable=False, server_default='5'))
        batch.add_column(sa.Column('last_match_run_at', sa.DateTime(),
                                   nullable=True))
        batch.add_column(sa.Column('last_match_matched', sa.Integer(),
                                   nullable=True))
        batch.add_column(sa.Column('last_match_total', sa.Integer(),
                                   nullable=True))

    with op.batch_alter_table('garden_subscription') as batch:
        batch.add_column(sa.Column('last_drip_day', sa.Integer(), nullable=True))

    with op.batch_alter_table('community_garden') as batch:
        batch.add_column(sa.Column('trial_nudge_sent_at', sa.DateTime(),
                                   nullable=True))


def downgrade():
    with op.batch_alter_table('community_garden') as batch:
        batch.drop_column('trial_nudge_sent_at')

    with op.batch_alter_table('garden_subscription') as batch:
        batch.drop_column('last_drip_day')

    with op.batch_alter_table('crm_agent_settings') as batch:
        batch.drop_column('last_match_total')
        batch.drop_column('last_match_matched')
        batch.drop_column('last_match_run_at')
        batch.drop_column('daily_ai_budget_usd')

    with op.batch_alter_table('crm_contact') as batch:
        batch.drop_index('ix_crm_contact_platform_status')
        batch.drop_column('nurture_cycles')
        batch.drop_column('platform_status_at')
        batch.drop_column('platform_status')
