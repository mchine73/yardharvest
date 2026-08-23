"""Record what Stripe actually charged, not what we assumed it charged.

The ledger only ever knew about the platform's own application fee, so
"You keep" was really "collected minus our cut". That is correct only while
the platform absorbs Stripe's processing fee. Once the connected account
bears it instead, the figure overstates every deposit by roughly 3% — on a
screen built so managers would not have to check Stripe.

``stripe_fee_cents`` holds the fee Stripe charged the *connected* account,
read from the balance transaction rather than inferred. NULL is meaningful
and deliberate: it means "not known yet", which is not zero. Zero is a fact
(the platform absorbed it); NULL means the lookup has not run or failed, and
the screens caveat the total instead of quietly under-reporting it.

Existing rows stay NULL — `flask stripe-backfill-fees` fills them in.

Revision ID: b8d0f2a4c6e8
Revises: a9c1e3f5b7d9
Create Date: 2026-08-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'b8d0f2a4c6e8'
down_revision = 'a9c1e3f5b7d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('garden_finance_event') as batch:
        batch.add_column(sa.Column('stripe_fee_cents', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('garden_finance_event') as batch:
        batch.drop_column('stripe_fee_cents')
