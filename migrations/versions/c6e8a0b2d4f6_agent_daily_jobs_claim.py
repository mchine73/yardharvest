"""Agent heartbeat: once-a-day housekeeping claim

crm_agent_settings.last_daily_jobs_date — the agent heartbeat now carries
the jobs that were supposed to ride Render's cron services (meeting
reminders, nurture resurfacing, the weekly CRM backup, garden trial
lifecycle). Those crons were never provisioned — Render has no free
instance type for cron — so this column is what makes repeated heartbeats
run that work exactly once per local day.

Revision ID: c6e8a0b2d4f6
Revises: b5d7f9a1c3e5
Create Date: 2026-08-18
"""
import sqlalchemy as sa
from alembic import op

revision = 'c6e8a0b2d4f6'
down_revision = 'b5d7f9a1c3e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_agent_settings') as b:
        b.add_column(sa.Column('last_daily_jobs_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('crm_agent_settings') as b:
        b.drop_column('last_daily_jobs_date')
