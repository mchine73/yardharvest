"""email unsubscribe suppression list

Global suppression list for bulk email (announcements, CRM campaigns), populated
by the List-Unsubscribe self-service page.

Revision ID: c3e5f7a9b1d3
Revises: b2c4d6e8f0a1
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3e5f7a9b1d3'
down_revision = 'b2c4d6e8f0a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_unsubscribe',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_unsubscribe_email'),
                    'email_unsubscribe', ['email'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_email_unsubscribe_email'), table_name='email_unsubscribe')
    op.drop_table('email_unsubscribe')
