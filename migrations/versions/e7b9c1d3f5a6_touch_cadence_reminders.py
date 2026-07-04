"""BDR touch cadence + booking reminders

crm_contact.followup_count — how many no-reply agent follow-ups have been sent
(drives 4d → 8d spacing and the auto-Nurture cap at 3).
booking.reminder_sent_at — stamps the 24h meeting reminder so the daily cron
sends it exactly once.

Revision ID: e7b9c1d3f5a6
Revises: d5f7a9b1c3e4
Create Date: 2026-07-04
"""
import sqlalchemy as sa
from alembic import op

revision = 'e7b9c1d3f5a6'
down_revision = 'd5f7a9b1c3e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as b:
        b.add_column(sa.Column('followup_count', sa.Integer(),
                               nullable=False, server_default='0'))
    with op.batch_alter_table('booking') as b:
        b.add_column(sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('booking') as b:
        b.drop_column('reminder_sent_at')
    with op.batch_alter_table('crm_contact') as b:
        b.drop_column('followup_count')
