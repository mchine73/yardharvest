"""Opaque prefixed public_ids for user + garden (replace 7-digit numerics)

Revision ID: a1b2c3d4e5f6
Revises: f7a9c1e3d5b7
Create Date: 2026-06-17

Widens user.public_id / community_garden.public_id from VARCHAR(7) to
VARCHAR(32) and regenerates EVERY existing row's public_id as an opaque,
CSPRNG-generated, prefixed token ("usr_…" / "grd_…") so no simple 7-digit
numeric ids remain. In-app navigation uses primary keys, so this does not break
SPA links; only stale external/notification links that embedded an old numeric
code are affected.

The generator is duplicated here (rather than imported from app.models) so the
migration stays self-contained and reproducible regardless of future app code.
"""
import secrets

import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f7a9c1e3d5b7'
branch_labels = None
depends_on = None

# Unambiguous base58-style alphabet (no 0/O/1/I/l) — keep in sync with
# app/models.py::_PUBLIC_ID_ALPHABET.
_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_TOKEN_LEN = 14


def _gen(prefix):
    return f"{prefix}_" + ''.join(secrets.choice(_ALPHABET) for _ in range(_TOKEN_LEN))


def _rekey(table_name, prefix):
    """Assign a fresh unique opaque public_id to every row in the table."""
    conn = op.get_bind()
    row_ids = [r[0] for r in conn.execute(sa.text(f'SELECT id FROM "{table_name}"')).fetchall()]
    used = set()
    for row_id in row_ids:
        cand = _gen(prefix)
        while cand in used:
            cand = _gen(prefix)
        used.add(cand)
        conn.execute(
            sa.text(f'UPDATE "{table_name}" SET public_id = :pid WHERE id = :rid'),
            {'pid': cand, 'rid': row_id})


def upgrade():
    with op.batch_alter_table('user') as b:
        b.alter_column('public_id', existing_type=sa.String(length=7),
                       type_=sa.String(length=32), existing_nullable=True)
    with op.batch_alter_table('community_garden') as b:
        b.alter_column('public_id', existing_type=sa.String(length=7),
                       type_=sa.String(length=32), existing_nullable=True)

    _rekey('user', 'usr')
    _rekey('community_garden', 'grd')


def downgrade():
    # Best-effort reversal: restore random 7-digit numeric ids and narrow back.
    import random

    conn = op.get_bind()
    for table_name in ('user', 'community_garden'):
        row_ids = [r[0] for r in conn.execute(sa.text(f'SELECT id FROM "{table_name}"')).fetchall()]
        used = set()
        for row_id in row_ids:
            cand = str(random.randint(1000000, 9999999))
            while cand in used:
                cand = str(random.randint(1000000, 9999999))
            used.add(cand)
            conn.execute(
                sa.text(f'UPDATE "{table_name}" SET public_id = :pid WHERE id = :rid'),
                {'pid': cand, 'rid': row_id})

    with op.batch_alter_table('community_garden') as b:
        b.alter_column('public_id', existing_type=sa.String(length=32),
                       type_=sa.String(length=7), existing_nullable=True)
    with op.batch_alter_table('user') as b:
        b.alter_column('public_id', existing_type=sa.String(length=32),
                       type_=sa.String(length=7), existing_nullable=True)
