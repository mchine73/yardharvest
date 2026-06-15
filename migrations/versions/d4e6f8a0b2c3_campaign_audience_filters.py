"""crm_campaign audience filter columns (sendable drafts)

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2
Create Date: 2026-06-14

Adds audience_state / audience_org_type / audience_tag to crm_campaign so an
AI-drafted (or manually saved) campaign can reconstruct its recipient audience
and be sent from the campaign detail page.
"""
import sqlalchemy as sa
from alembic import op

revision = 'd4e6f8a0b2c3'
down_revision = 'c3d5e7f9a1b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_campaign') as batch:
        batch.add_column(sa.Column('audience_state', sa.String(length=20), nullable=True))
        batch.add_column(sa.Column('audience_org_type', sa.String(length=40), nullable=True))
        batch.add_column(sa.Column('audience_tag', sa.String(length=80), nullable=True))


def downgrade():
    with op.batch_alter_table('crm_campaign') as batch:
        batch.drop_column('audience_tag')
        batch.drop_column('audience_org_type')
        batch.drop_column('audience_state')
