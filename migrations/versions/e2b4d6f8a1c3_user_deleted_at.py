"""Mark an account as erased.

The user row cannot be deleted outright: 46 tables reference it and almost all
of those foreign keys are NOT NULL, so a real DELETE either fails on a
constraint or cascades through records belonging to other people - the dues
ledger, a comment thread, the plot history. The row stays as a tombstone with
its personal fields scrubbed, and this column is what marks it as one.

Revision ID: e2b4d6f8a1c3
Revises: d1f3a5c7e9b2
"""
import sqlalchemy as sa
from alembic import op

revision = 'e2b4d6f8a1c3'
down_revision = 'd1f3a5c7e9b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('deleted_at')
