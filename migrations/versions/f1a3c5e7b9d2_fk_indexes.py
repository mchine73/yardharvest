"""Add indexes on hot foreign-key columns

SQLAlchemy does not auto-index foreign keys, so the dominant query pattern in
this app — filtering child rows by garden_id (every admin/garden page), plus a
handful of other hot lookups and the CRM pipeline FKs — was doing sequential
scans. This adds covering indexes for those columns. Index-only migration; no
data change.

Revision ID: f1a3c5e7b9d2
Revises: e6a8c2d4f0b6
Create Date: 2026-06-20
"""
from alembic import op

revision = 'f1a3c5e7b9d2'
down_revision = 'e6a8c2d4f0b6'
branch_labels = None
depends_on = None

# (table, column) pairs to index. Curated to the genuinely hot paths rather than
# all 120 unindexed FKs — garden_id children, per-row count lookups, the
# my-gardens/notifications/inbox user lookups, and the CRM pipeline.
_INDEXES = [
    # garden_id on child tables (filtered on virtually every garden/admin view)
    ('garden_plot', 'garden_id'),
    ('garden_dues_record', 'garden_id'),
    ('garden_expense', 'garden_id'),
    ('garden_event', 'garden_id'),
    ('garden_announcement', 'garden_id'),
    ('garden_comment', 'garden_id'),
    ('garden_message', 'garden_id'),
    ('garden_photo', 'garden_id'),
    ('garden_membership', 'garden_id'),
    ('garden_waitlist', 'garden_id'),
    ('harvest_log', 'garden_id'),
    ('shared_resource', 'garden_id'),
    ('volunteer_shift', 'garden_id'),
    ('garden_weather_alert', 'garden_id'),
    ('plot_assignment_history', 'garden_id'),
    ('resource_checkout_log', 'garden_id'),
    ('notification', 'garden_id'),
    # per-row count / child lookups
    ('event_rsvp', 'event_id'),
    ('shift_signup', 'shift_id'),
    ('garden_comment', 'parent_id'),
    ('resource_checkout_log', 'resource_id'),
    ('plot_assignment_history', 'plot_id'),
    # user-centric hot lookups (my-gardens, notifications, inbox)
    ('garden_plot', 'assigned_to_id'),
    ('garden_waitlist', 'user_id'),
    ('notification', 'user_id'),
    ('garden_message', 'recipient_id'),
    ('garden_dues_record', 'user_id'),
    # CRM pipeline
    ('crm_contact', 'company_id'),
    ('crm_deal', 'company_id'),
    ('crm_deal', 'contact_id'),
    ('crm_deal', 'owner_id'),
    ('crm_task', 'contact_id'),
    ('crm_task', 'deal_id'),
    ('crm_activity', 'contact_id'),
    ('crm_activity', 'deal_id'),
    ('crm_note', 'contact_id'),
    ('crm_note', 'deal_id'),
    ('crm_campaign_recipient', 'campaign_id'),
    ('crm_campaign_recipient', 'contact_id'),
    # marketplace order lookups
    ('order', 'buyer_id'),
    ('order', 'seller_id'),
]


def upgrade():
    for tbl, col in _INDEXES:
        op.create_index(f'ix_{tbl}_{col}', tbl, [col])


def downgrade():
    for tbl, col in _INDEXES:
        op.drop_index(f'ix_{tbl}_{col}', table_name=tbl)
