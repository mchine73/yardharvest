"""CRM contact email-deliverability / bounce tracking

Adds soft-bounce strike tracking + last-bounce metadata to crm_contact so the
ZeptoMail webhook can record soft bounces (and only suppress after a threshold),
hard bounces, and complaints, and the CRM can surface delivery health per
contact.

Revision ID: f9b1d3a5c7e9
Revises: e8a0c2d4f6b8
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'f9b1d3a5c7e9'
down_revision = 'e8a0c2d4f6b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as b:
        b.add_column(sa.Column('soft_bounce_count', sa.Integer(),
                               nullable=False, server_default='0'))
        b.add_column(sa.Column('last_bounce_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('last_bounce_type', sa.String(length=12), nullable=True))
        b.add_column(sa.Column('last_bounce_reason', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('crm_contact') as b:
        b.drop_column('last_bounce_reason')
        b.drop_column('last_bounce_type')
        b.drop_column('last_bounce_at')
        b.drop_column('soft_bounce_count')
