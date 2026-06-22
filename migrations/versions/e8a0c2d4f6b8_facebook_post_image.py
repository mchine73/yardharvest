"""Facebook post image_url

Adds an optional ``image_url`` column to crm_facebook_post so a post can carry
a photo. When set, the CRM publishes the post via the Graph /{page}/photos
endpoint (url + caption) instead of /{page}/feed.

Revision ID: e8a0c2d4f6b8
Revises: d6f8b0c2e4a7
Create Date: 2026-06-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'e8a0c2d4f6b8'
down_revision = 'd6f8b0c2e4a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crm_facebook_post') as b:
        b.add_column(sa.Column('image_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('crm_facebook_post') as b:
        b.drop_column('image_url')
