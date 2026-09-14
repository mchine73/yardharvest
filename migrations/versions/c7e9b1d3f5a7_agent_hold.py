"""Let a human claim a lead the autonomous cycle would otherwise email.

lead_status already draws the line between the agent's leads (New/Working)
and a person's (Engaged/Qualified), but that boundary only moves when the
lead's stage genuinely changes. A lead you mean to phone yourself is still,
factually, 'Working' — so before this the only way to claim one was to
misstate its stage.

Revision ID: c7e9b1d3f5a7
Revises: b8d0f2a4c6e8
"""
import sqlalchemy as sa
from alembic import op

revision = 'c7e9b1d3f5a7'
down_revision = 'b8d0f2a4c6e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_contact') as batch:
        batch.add_column(sa.Column('agent_hold', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('crm_contact') as batch:
        batch.drop_column('agent_hold')
