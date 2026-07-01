"""Booking (scheduling page → Zoho calendar)

Creates the four tables behind the public /book scheduling page:
booking_settings (singleton config), booking_type (meeting types),
booking_availability (weekly windows), and booking (confirmed appointments).

Revision ID: c4e6f8a0b2d3
Revises: b3d5f7a9c1e2
Create Date: 2026-06-30
"""
import sqlalchemy as sa
from alembic import op

revision = 'c4e6f8a0b2d3'
down_revision = 'b3d5f7a9c1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'booking_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='America/Chicago'),
        sa.Column('owner_name', sa.String(length=120), nullable=True),
        sa.Column('heading', sa.String(length=160), nullable=True),
        sa.Column('intro', sa.Text(), nullable=True),
        sa.Column('min_notice_hours', sa.Integer(), nullable=False, server_default='12'),
        sa.Column('max_advance_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('slot_granularity_min', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('max_per_day', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('block_zoho_busy', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'booking_type',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(length=32), nullable=True),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('buffer_before_min', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('buffer_after_min', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('color', sa.String(length=7), nullable=True, server_default='#5b8c3e'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_booking_type_public_id', 'booking_type', ['public_id'], unique=True)
    op.create_index('ix_booking_type_slug', 'booking_type', ['slug'], unique=True)
    op.create_index('ix_booking_type_is_active', 'booking_type', ['is_active'])

    op.create_table(
        'booking_availability',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_min', sa.Integer(), nullable=False),
        sa.Column('end_min', sa.Integer(), nullable=False),
    )

    op.create_table(
        'booking',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(length=32), nullable=True),
        sa.Column('booking_type_id', sa.Integer(), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('invitee_timezone', sa.String(length=64), nullable=True),
        sa.Column('invitee_name', sa.String(length=120), nullable=False),
        sa.Column('invitee_email', sa.String(length=120), nullable=False),
        sa.Column('invitee_phone', sa.String(length=30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='confirmed'),
        sa.Column('zoho_event_uid', sa.String(length=255), nullable=True),
        sa.Column('zoho_sync_status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('zoho_sync_error', sa.String(length=255), nullable=True),
        sa.Column('crm_contact_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['booking_type_id'], ['booking_type.id']),
    )
    op.create_index('ix_booking_public_id', 'booking', ['public_id'], unique=True)
    op.create_index('ix_booking_start_at', 'booking', ['start_at'])
    op.create_index('ix_booking_invitee_email', 'booking', ['invitee_email'])
    op.create_index('ix_booking_status', 'booking', ['status'])

    # --- Seed a starter config so /book is functional immediately on deploy.
    # All of this is editable in the admin UI (/admin/booking).
    settings_t = sa.table(
        'booking_settings',
        sa.column('id', sa.Integer), sa.column('timezone', sa.String),
        sa.column('owner_name', sa.String), sa.column('heading', sa.String),
        sa.column('intro', sa.Text), sa.column('min_notice_hours', sa.Integer),
        sa.column('max_advance_days', sa.Integer),
        sa.column('slot_granularity_min', sa.Integer),
        sa.column('max_per_day', sa.Integer), sa.column('block_zoho_busy', sa.Boolean))
    op.bulk_insert(settings_t, [{
        'id': 1, 'timezone': 'America/Chicago', 'owner_name': 'James Goodman',
        'heading': 'Book time with James',
        'intro': 'Pick a meeting type and a time that works for you.',
        'min_notice_hours': 12, 'max_advance_days': 30,
        'slot_granularity_min': 30, 'max_per_day': 0, 'block_zoho_busy': True,
    }])

    type_t = sa.table(
        'booking_type',
        sa.column('slug', sa.String), sa.column('name', sa.String),
        sa.column('description', sa.Text), sa.column('duration_min', sa.Integer),
        sa.column('location', sa.String), sa.column('buffer_before_min', sa.Integer),
        sa.column('buffer_after_min', sa.Integer), sa.column('color', sa.String),
        sa.column('is_active', sa.Boolean), sa.column('sort_order', sa.Integer))
    op.bulk_insert(type_t, [{
        'slug': 'intro-call', 'name': 'Intro Call',
        'description': 'A quick 30-minute introduction.',
        'duration_min': 30, 'location': 'Phone call',
        'buffer_before_min': 0, 'buffer_after_min': 0,
        'color': '#5b8c3e', 'is_active': True, 'sort_order': 1,
    }])

    avail_t = sa.table('booking_availability',
                       sa.column('day_of_week', sa.Integer),
                       sa.column('start_min', sa.Integer),
                       sa.column('end_min', sa.Integer))
    # Monday–Friday, 09:00–17:00 (owner-local).
    op.bulk_insert(avail_t, [{'day_of_week': d, 'start_min': 540, 'end_min': 1020}
                             for d in range(0, 5)])


def downgrade():
    op.drop_index('ix_booking_status', table_name='booking')
    op.drop_index('ix_booking_invitee_email', table_name='booking')
    op.drop_index('ix_booking_start_at', table_name='booking')
    op.drop_index('ix_booking_public_id', table_name='booking')
    op.drop_table('booking')
    op.drop_table('booking_availability')
    op.drop_index('ix_booking_type_is_active', table_name='booking_type')
    op.drop_index('ix_booking_type_slug', table_name='booking_type')
    op.drop_index('ix_booking_type_public_id', table_name='booking_type')
    op.drop_table('booking_type')
    op.drop_table('booking_settings')
