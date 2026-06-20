"""photo likes + comments (garden photo wall social)

Adds a denormalized likes_count to photo and two child tables — photo_like
(one upvote per user per photo) and photo_comment — so the garden photo wall
supports upvoting and comments, matching the community-wall experience.

Revision ID: e6a8c2d4f0b6
Revises: d4f6a8c0e2b4
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6a8c2d4f0b6'
down_revision = 'd4f6a8c0e2b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('photo', schema=None) as b:
        b.add_column(sa.Column('likes_count', sa.Integer(), nullable=True, server_default='0'))

    op.create_table(
        'photo_like',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['photo_id'], ['photo.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('photo_id', 'user_id', name='uq_photo_like'),
    )
    op.create_index(op.f('ix_photo_like_photo_id'), 'photo_like', ['photo_id'])

    op.create_table(
        'photo_comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['photo_id'], ['photo.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_photo_comment_photo_id'), 'photo_comment', ['photo_id'])


def downgrade():
    op.drop_index(op.f('ix_photo_comment_photo_id'), table_name='photo_comment')
    op.drop_table('photo_comment')
    op.drop_index(op.f('ix_photo_like_photo_id'), table_name='photo_like')
    op.drop_table('photo_like')
    with op.batch_alter_table('photo', schema=None) as b:
        b.drop_column('likes_count')
