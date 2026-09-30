"""Member reporting of wall posts, and member-to-member blocking

App Store guideline 1.2 requires an app carrying user-generated content to let
any member report objectionable content and block an abusive member. The wall
already had automated filtering and an organizer moderation queue; these two
tables add the member-facing half.

`comment_report` is one row per person per comment, resolved when an organizer
approves or deletes the post. `user_block` is one-directional and affects only
the blocker's own view of the wall.

Revision ID: c4e6a8b0d2f4
Revises: e2b4d6f8a1c3
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4e6a8b0d2f4'
down_revision = 'e2b4d6f8a1c3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comment_report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=40), nullable=False,
                  server_default='other'),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['garden_comment.id']),
        sa.ForeignKeyConstraint(['reporter_id'], ['user.id']),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'reporter_id',
                            name='uq_comment_report'),
    )
    op.create_index('ix_comment_report_comment_id', 'comment_report',
                    ['comment_id'])

    op.create_table(
        'user_block',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('blocker_id', sa.Integer(), nullable=False),
        sa.Column('blocked_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['blocker_id'], ['user.id']),
        sa.ForeignKeyConstraint(['blocked_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_user_block'),
    )
    op.create_index('ix_user_block_blocker_id', 'user_block', ['blocker_id'])


def downgrade():
    op.drop_index('ix_user_block_blocker_id', table_name='user_block')
    op.drop_table('user_block')
    op.drop_index('ix_comment_report_comment_id', table_name='comment_report')
    op.drop_table('comment_report')
