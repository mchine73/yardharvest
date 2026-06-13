"""public_id on user+garden, garden_comment wall, subscription.admin_granted

Revision ID: b1f3a7c2d4e5
Revises: 65a912bb5140
Create Date: 2026-06-13

Adds:
- user.public_id / community_garden.public_id (random 7-digit public codes),
  backfilled for existing rows and uniquely indexed.
- garden_comment table (public comment wall).
- garden_subscription.admin_granted (suppresses the cancellation banner for
  admin-granted Pro).
"""
import random

import sqlalchemy as sa
from alembic import op

revision = 'b1f3a7c2d4e5'
down_revision = '65a912bb5140'
branch_labels = None
depends_on = None


def _backfill_public_ids(table_name):
    """Assign a unique random 7-digit public_id to every existing row."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(f'SELECT id FROM "{table_name}" WHERE public_id IS NULL')).fetchall()
    used = {r[0] for r in conn.execute(
        sa.text(f'SELECT public_id FROM "{table_name}" WHERE public_id IS NOT NULL')).fetchall()}
    for (row_id,) in rows:
        while True:
            cand = str(random.randint(1000000, 9999999))
            if cand not in used:
                used.add(cand)
                break
        conn.execute(
            sa.text(f'UPDATE "{table_name}" SET public_id = :pid WHERE id = :rid'),
            {'pid': cand, 'rid': row_id})


def upgrade():
    op.add_column('user', sa.Column('public_id', sa.String(length=7), nullable=True))
    op.add_column('community_garden', sa.Column('public_id', sa.String(length=7), nullable=True))
    op.add_column('garden_subscription', sa.Column('admin_granted', sa.Boolean(), nullable=True))

    op.create_table(
        'garden_comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('garden_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('moderation_reason', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['garden_id'], ['community_garden.id']),
        sa.ForeignKeyConstraint(['author_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    _backfill_public_ids('user')
    _backfill_public_ids('community_garden')

    op.create_index('ix_user_public_id', 'user', ['public_id'], unique=True)
    op.create_index('ix_community_garden_public_id', 'community_garden', ['public_id'], unique=True)


def downgrade():
    op.drop_index('ix_community_garden_public_id', table_name='community_garden')
    op.drop_index('ix_user_public_id', table_name='user')
    op.drop_table('garden_comment')
    op.drop_column('garden_subscription', 'admin_granted')
    op.drop_column('community_garden', 'public_id')
    op.drop_column('user', 'public_id')
