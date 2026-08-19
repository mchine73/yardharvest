"""Retire the marketplace-era email tagline.

Every platform email header carried "Neighbors gardening with neighbors" — the
tagline from when YardHarvest was a neighbour-to-neighbour produce marketplace.
The product is a community-garden operating system now, and the site says
"Less admin, more garden" everywhere else. The value was set by hand in the
admin email-branding screen, so a column default could never correct it.

Deliberately narrow: it rewrites that exact string and nothing else. Any other
tagline is somebody's live decision and is left alone. The companion header
colour problem needs no migration — email_service.header_band_color() now
falls back to the brand ink whenever the configured colour fails contrast
against the white wordmark, which is what the leftover green was doing.

Revision ID: a1c3e5b7d9f2
Revises: d7f9b1c3e5a7
Create Date: 2026-08-19
"""
import sqlalchemy as sa
from alembic import op

revision = 'a1c3e5b7d9f2'
down_revision = 'd7f9b1c3e5a7'
branch_labels = None
depends_on = None

_MARKETPLACE_TAGLINE = 'Neighbors gardening with neighbors'
_CURRENT_TAGLINE = 'Less admin, more garden'


def _swap(old, new):
    op.execute(
        sa.text('UPDATE site_email_config SET tagline = :new WHERE tagline = :old')
        .bindparams(new=new, old=old)
    )


def upgrade():
    _swap(_MARKETPLACE_TAGLINE, _CURRENT_TAGLINE)


def downgrade():
    _swap(_CURRENT_TAGLINE, _MARKETPLACE_TAGLINE)
