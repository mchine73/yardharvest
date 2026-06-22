"""CRM campaign open/click tracking

Adds per-recipient tracking columns to crm_campaign_recipient: a unique `token`
(used in the open pixel + click-redirect URLs) and `opened_at` / `clicked_at`
timestamps. First-party engagement tracking for outbound campaigns.

Revision ID: d6f8b0c2e4a7
Revises: c5e7a9b1d3f5
Create Date: 2026-06-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'd6f8b0c2e4a7'
down_revision = 'c5e7a9b1d3f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_campaign_recipient') as b:
        b.add_column(sa.Column('token', sa.String(length=48), nullable=True))
        b.add_column(sa.Column('opened_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('clicked_at', sa.DateTime(), nullable=True))
        b.create_index('ix_crm_campaign_recipient_token', ['token'])


def downgrade():
    with op.batch_alter_table('crm_campaign_recipient') as b:
        b.drop_index('ix_crm_campaign_recipient_token')
        b.drop_column('clicked_at')
        b.drop_column('opened_at')
        b.drop_column('token')
