"""Add pricing_config.dues_require_payout_ready (admin switch)

When True (default), online garden dues are refused unless the manager has
completed Stripe Connect payout onboarding (so every charge routes to them).
When False, dues fall back to a platform charge if the manager isn't ready.

Revision ID: e5f7a9b1c3d4
Revises: d4e6f8a0b2c3
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f7a9b1c3d4'
down_revision = 'd4e6f8a0b2c3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'pricing_config',
        sa.Column('dues_require_payout_ready', sa.Boolean(),
                  nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column('pricing_config', 'dues_require_payout_ready')
