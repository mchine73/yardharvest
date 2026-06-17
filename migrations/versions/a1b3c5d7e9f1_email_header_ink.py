"""Reset legacy default email header color to the redesign ink.

The email template's brand elements (lime CTA, ink headings, Onest, card) are
now hardcoded, but the header bar still honors the admin-set header_color. Reset
rows still on the OLD default green so existing installs conform to the redesign
without a manual settings change. Custom colors are left untouched.

Revision ID: a1b3c5d7e9f1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17
"""
from alembic import op


revision = 'a1b3c5d7e9f1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE site_email_config SET header_color = '#22242a' "
               "WHERE header_color IN ('#166f4c', '#2d6a2e')")


def downgrade():
    op.execute("UPDATE site_email_config SET header_color = '#166f4c' "
               "WHERE header_color = '#22242a'")
