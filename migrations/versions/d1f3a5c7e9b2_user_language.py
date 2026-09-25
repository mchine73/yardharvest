"""Remember which language each person reads the product in.

Needed before any translation ships, because the value it stores is read in
two different places: the language a request is answered in, and — the one
that actually matters — the language an email is written in. A notification is
composed for its recipient, who is rarely the person whose click triggered it.

Revision ID: d1f3a5c7e9b2
Revises: c7e9b1d3f5a7
"""
import sqlalchemy as sa
from alembic import op

revision = 'd1f3a5c7e9b2'
down_revision = 'c7e9b1d3f5a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('language', sa.String(length=5),
                                   nullable=False, server_default='en'))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('language')
