"""API usage ledger, and a history of messages to garden managers

`api_usage_event` is one row per call to a metered third-party API (an email
send, an SMS, a model call), written on its own connection so it never commits
or rolls back the request it happened in. It backs the admin API Usage page.

`manager_broadcast` is the audit trail for platform-to-garden-manager
messages: what was sent, to which audience, and how many it reached.

Revision ID: f3a5c7e9b1d4
Revises: c4e6a8b0d2f4
Create Date: 2026-10-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a5c7e9b1d4'
down_revision = 'c4e6a8b0d2f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_usage_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('operation', sa.String(length=40), nullable=False),
        sa.Column('units', sa.Integer(), nullable=True),
        sa.Column('ok', sa.Boolean(), nullable=True),
        sa.Column('model', sa.String(length=60), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('error', sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('api_usage_event', schema=None) as batch_op:
        batch_op.create_index('ix_api_usage_event_created_at', ['created_at'])
        batch_op.create_index('ix_api_usage_event_provider', ['provider'])
        batch_op.create_index('ix_api_usage_event_ok', ['ok'])

    op.create_table(
        'manager_broadcast',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('sender_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('audience', sa.Text(), nullable=True),
        sa.Column('channels', sa.String(length=40), nullable=True),
        sa.Column('recipient_count', sa.Integer(), nullable=True),
        sa.Column('emailed', sa.Integer(), nullable=True),
        sa.Column('email_failed', sa.Integer(), nullable=True),
        sa.Column('suppressed', sa.Integer(), nullable=True),
        sa.Column('notified', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('manager_broadcast', schema=None) as batch_op:
        batch_op.create_index('ix_manager_broadcast_created_at', ['created_at'])


def downgrade():
    with op.batch_alter_table('manager_broadcast', schema=None) as batch_op:
        batch_op.drop_index('ix_manager_broadcast_created_at')
    op.drop_table('manager_broadcast')
    with op.batch_alter_table('api_usage_event', schema=None) as batch_op:
        batch_op.drop_index('ix_api_usage_event_ok')
        batch_op.drop_index('ix_api_usage_event_provider')
        batch_op.drop_index('ix_api_usage_event_created_at')
    op.drop_table('api_usage_event')
