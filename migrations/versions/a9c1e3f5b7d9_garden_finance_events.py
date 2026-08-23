"""Give garden managers a record of their own Stripe money.

Everything a manager collected lived only in the Stripe dashboard. A
Tap-to-Pay sale left no trace in YardHarvest at all, a refund or chargeback
issued from Stripe never reached the roster, and "when does this reach my
bank" had no answer in the app.

* ``garden_finance_event`` — one row per money event the Stripe webhooks
  report: payments (online dues, in-person dues, ad-hoc sales), refunds,
  disputes, payouts and connected-account status changes. Written only by
  ``webhook_api``, so it reflects what Stripe did rather than what the app
  hoped. Garden-scoped rows carry ``garden_id``; account-level rows (payouts,
  account status) carry ``user_id`` instead, because a payout can span several
  gardens and folding it into one would make that garden's totals wrong.
* ``user.stripe_*`` — the connected account's health, mirrored from
  ``account.updated`` so a restriction is visible before a tap fails in front
  of a member, and so the finance screens need no Stripe round-trip.

Revision ID: a9c1e3f5b7d9
Revises: c3e5a7b9d1f4
Create Date: 2026-08-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'a9c1e3f5b7d9'
down_revision = 'c3e5a7b9d1f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'garden_finance_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('garden_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('source', sa.String(length=24), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=True),
        sa.Column('stripe_object_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_charge_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_event_id', sa.String(length=255), nullable=True),
        sa.Column('connected_account_id', sa.String(length=255), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=True),
        sa.Column('fee_cents', sa.Integer(), nullable=True),
        sa.Column('net_cents', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('counterparty', sa.String(length=160), nullable=True),
        sa.Column('dues_id', sa.Integer(), nullable=True),
        sa.Column('collected_by_id', sa.Integer(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['garden_id'], ['community_garden.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['dues_id'], ['garden_dues_record.id']),
        sa.ForeignKeyConstraint(['collected_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('garden_finance_event') as batch:
        batch.create_index('ix_garden_finance_event_garden_id', ['garden_id'])
        batch.create_index('ix_garden_finance_event_user_id', ['user_id'])
        batch.create_index('ix_garden_finance_event_kind', ['kind'])
        batch.create_index('ix_garden_finance_event_stripe_object_id',
                           ['stripe_object_id'])
        batch.create_index('ix_garden_finance_event_stripe_charge_id',
                           ['stripe_charge_id'])
        batch.create_index('ix_garden_finance_event_occurred_at', ['occurred_at'])
        # The feed query (one garden, newest first) and the webhook upsert
        # lookup (kind + object id) are the only two hot paths.
        batch.create_index('ix_garden_finance_event_garden_time',
                           ['garden_id', 'occurred_at'])
        batch.create_index('ix_garden_finance_event_upsert',
                           ['kind', 'stripe_object_id'])

    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('stripe_charges_enabled', sa.Boolean(),
                                   nullable=True, server_default=sa.false()))
        batch.add_column(sa.Column('stripe_payouts_enabled', sa.Boolean(),
                                   nullable=True, server_default=sa.false()))
        batch.add_column(sa.Column('stripe_requirements_due', sa.Text(),
                                   nullable=True))
        batch.add_column(sa.Column('stripe_disabled_reason', sa.String(length=120),
                                   nullable=True))
        batch.add_column(sa.Column('stripe_account_synced_at', sa.DateTime(),
                                   nullable=True))

    # Seed the two capability flags from what onboarding already told us, so
    # existing payout-ready managers don't read as "action needed" until their
    # first account.updated arrives. synced_at stays NULL on purpose — it is
    # what tells the UI (and us) that no Connect webhook has landed yet.
    op.execute('UPDATE "user" SET stripe_charges_enabled = true, '
               'stripe_payouts_enabled = true '
               'WHERE stripe_onboarding_complete = true')


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('stripe_account_synced_at')
        batch.drop_column('stripe_disabled_reason')
        batch.drop_column('stripe_requirements_due')
        batch.drop_column('stripe_payouts_enabled')
        batch.drop_column('stripe_charges_enabled')

    with op.batch_alter_table('garden_finance_event') as batch:
        batch.drop_index('ix_garden_finance_event_upsert')
        batch.drop_index('ix_garden_finance_event_garden_time')
        batch.drop_index('ix_garden_finance_event_occurred_at')
        batch.drop_index('ix_garden_finance_event_stripe_charge_id')
        batch.drop_index('ix_garden_finance_event_stripe_object_id')
        batch.drop_index('ix_garden_finance_event_kind')
        batch.drop_index('ix_garden_finance_event_user_id')
        batch.drop_index('ix_garden_finance_event_garden_id')
    op.drop_table('garden_finance_event')
