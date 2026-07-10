"""Agent-run failure detail

crm_agent_run.error — short failure detail recorded when a background
drafting job dies (status='failed'), so the console can tell "the run
failed — try again" apart from "ran fine, found nothing new".

Revision ID: a4c6e8b0d2f4
Revises: e7b9c1d3f5a6
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op

revision = 'a4c6e8b0d2f4'
down_revision = 'e7b9c1d3f5a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_agent_run') as b:
        b.add_column(sa.Column('error', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('crm_agent_run') as b:
        b.drop_column('error')
