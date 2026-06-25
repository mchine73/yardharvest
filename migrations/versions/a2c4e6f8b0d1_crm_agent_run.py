"""CRM agent drafting-run tracking

Adds crm_agent_run so the BDR console can tell when a background drafting job
has finished (across any gunicorn worker) and stop the "drafting…" banner —
instead of guessing from the pending-proposal count.

Revision ID: a2c4e6f8b0d1
Revises: f9b1d3a5c7e9
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'a2c4e6f8b0d1'
down_revision = 'f9b1d3a5c7e9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_agent_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('crm_agent_run') as b:
        b.create_index('ix_crm_agent_run_status', ['status'])
        b.create_index('ix_crm_agent_run_created_at', ['created_at'])


def downgrade():
    with op.batch_alter_table('crm_agent_run') as b:
        b.drop_index('ix_crm_agent_run_created_at')
        b.drop_index('ix_crm_agent_run_status')
    op.drop_table('crm_agent_run')
