"""shared_resource.out_of_service + service_note (tool service status)

Revision ID: c3d5e7f9a1b2
Revises: b1f3a7c2d4e5
Create Date: 2026-06-13

Adds admin tool-management fields:
- shared_resource.out_of_service (bool) — pulled for repair/maintenance; the
  tool stays in inventory but cannot be checked out until returned to service.
- shared_resource.service_note (str) — optional reason shown to admins.
"""
import sqlalchemy as sa
from alembic import op

revision = 'c3d5e7f9a1b2'
down_revision = 'b1f3a7c2d4e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('shared_resource') as batch:
        batch.add_column(sa.Column(
            'out_of_service', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('service_note', sa.String(length=300), nullable=True))
    # Drop the server_default now that existing rows are populated; the model
    # default handles new rows.
    with op.batch_alter_table('shared_resource') as batch:
        batch.alter_column('out_of_service', server_default=None)


def downgrade():
    with op.batch_alter_table('shared_resource') as batch:
        batch.drop_column('service_note')
        batch.drop_column('out_of_service')
