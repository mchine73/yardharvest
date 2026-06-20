"""garden layout designer: plot spans + rounded + layout features (dead zones)

Adds rectangular plot spans (grid_width/grid_height) and a rounded flag to
garden_plot, plus a garden_layout_feature table for non-plot map elements
(sheds, tables, paths, landscaping, public areas, water, compost).

Revision ID: d4f6a8c0e2b4
Revises: c3e5f7a9b1d3
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4f6a8c0e2b4'
down_revision = 'c3e5f7a9b1d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('garden_plot', schema=None) as b:
        b.add_column(sa.Column('grid_width', sa.Integer(), nullable=True, server_default='1'))
        b.add_column(sa.Column('grid_height', sa.Integer(), nullable=True, server_default='1'))
        b.add_column(sa.Column('rounded', sa.Boolean(), nullable=True, server_default=sa.false()))

    op.create_table(
        'garden_layout_feature',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('garden_id', sa.Integer(), nullable=False),
        sa.Column('feature_type', sa.String(length=30), nullable=False),
        sa.Column('label', sa.String(length=60), nullable=True),
        sa.Column('grid_row', sa.Integer(), nullable=False),
        sa.Column('grid_col', sa.Integer(), nullable=False),
        sa.Column('grid_width', sa.Integer(), nullable=True),
        sa.Column('grid_height', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('rounded', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['garden_id'], ['community_garden.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_garden_layout_feature_garden_id'),
                    'garden_layout_feature', ['garden_id'])


def downgrade():
    op.drop_index(op.f('ix_garden_layout_feature_garden_id'), table_name='garden_layout_feature')
    op.drop_table('garden_layout_feature')
    with op.batch_alter_table('garden_plot', schema=None) as b:
        b.drop_column('rounded')
        b.drop_column('grid_height')
        b.drop_column('grid_width')
