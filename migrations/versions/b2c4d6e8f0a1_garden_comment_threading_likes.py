"""garden comment threading + per-comment likes

Adds one-level threading (parent_id) and a denormalized likes_count to
garden_comment, plus a garden_comment_like table (one like per user per comment).

Revision ID: b2c4d6e8f0a1
Revises: a1b3c5d7e9f1
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c4d6e8f0a1'
down_revision = 'a1b3c5d7e9f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('garden_comment', schema=None) as batch:
        batch.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('likes_count', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_garden_comment_parent', 'garden_comment', ['parent_id'], ['id'])

    op.create_table(
        'garden_comment_like',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['garden_comment.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', name='uq_garden_comment_like'),
    )


def downgrade():
    op.drop_table('garden_comment_like')
    with op.batch_alter_table('garden_comment', schema=None) as batch:
        batch.drop_constraint('fk_garden_comment_parent', type_='foreignkey')
        batch.drop_column('likes_count')
        batch.drop_column('parent_id')
