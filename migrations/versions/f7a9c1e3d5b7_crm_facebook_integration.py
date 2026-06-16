"""CRM Facebook integration: connected Page, posts, inbox message cache.

Revision ID: f7a9c1e3d5b7
Revises: e5f7a9b1c3d4
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a9c1e3d5b7'
down_revision = 'e5f7a9b1c3d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_facebook_account',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('page_id', sa.String(length=64), nullable=False),
        sa.Column('page_name', sa.String(length=160)),
        sa.Column('page_access_token', sa.Text(), nullable=False),
        sa.Column('user_access_token', sa.Text()),
        sa.Column('token_expires_at', sa.DateTime()),
        sa.Column('active', sa.Boolean(), server_default=sa.true()),
        sa.Column('connected_by_id', sa.Integer(), sa.ForeignKey('crm_user.id')),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_table(
        'crm_facebook_post',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(length=500)),
        sa.Column('status', sa.String(length=20), server_default='draft'),
        sa.Column('scheduled_for', sa.DateTime()),
        sa.Column('published_at', sa.DateTime()),
        sa.Column('fb_post_id', sa.String(length=80)),
        sa.Column('error', sa.String(length=400)),
        sa.Column('content_item_id', sa.Integer(), sa.ForeignKey('crm_content_item.id')),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('crm_user.id')),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_table(
        'crm_facebook_message',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.String(length=120)),
        sa.Column('fb_message_id', sa.String(length=120), unique=True),
        sa.Column('sender_id', sa.String(length=64)),
        sa.Column('sender_name', sa.String(length=160)),
        sa.Column('direction', sa.String(length=4)),
        sa.Column('text', sa.Text()),
        sa.Column('created_time', sa.DateTime()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_crm_facebook_message_conversation_id',
                    'crm_facebook_message', ['conversation_id'])


def downgrade():
    op.drop_index('ix_crm_facebook_message_conversation_id',
                  table_name='crm_facebook_message')
    op.drop_table('crm_facebook_message')
    op.drop_table('crm_facebook_post')
    op.drop_table('crm_facebook_account')
