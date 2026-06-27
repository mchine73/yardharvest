"""CRM agent run usage + cost tracking

Adds per-run usage columns to crm_agent_run (model, token counts, web search
count, estimated cost) so the BDR console can show AI spend visibility.

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-06-25
"""
import sqlalchemy as sa
from alembic import op

revision = 'b3d5f7a9c1e2'
down_revision = 'a2c4e6f8b0d1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_agent_run') as b:
        b.add_column(sa.Column('model', sa.String(length=40), nullable=True))
        b.add_column(sa.Column('input_tokens', sa.Integer(), nullable=True, server_default='0'))
        b.add_column(sa.Column('output_tokens', sa.Integer(), nullable=True, server_default='0'))
        b.add_column(sa.Column('web_searches', sa.Integer(), nullable=True, server_default='0'))
        b.add_column(sa.Column('cost_usd', sa.Float(), nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('crm_agent_run') as b:
        b.drop_column('cost_usd')
        b.drop_column('web_searches')
        b.drop_column('output_tokens')
        b.drop_column('input_tokens')
        b.drop_column('model')
