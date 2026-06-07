#!/usr/bin/env python3
"""One-off migration from yardharvest-crm-db (standalone CRM) to the main
yardharvest-db, renaming every CRM table to ``crm_*`` along the way.

The old CRM stored tables under their natural names (``user``, ``company``,
``contact``, ``deal``, ``note``, ``task``, ``deal_contact``, ``email_template``,
``campaign``, ``campaign_recipient``, ``activity``). The consolidated app
stores them under ``crm_user``, ``crm_company``, ``crm_contact`` etc. so the
``user`` table doesn't collide with YH's own ``user`` table.

USAGE (run locally, with both ``DATABASE_URL`` strings handy):

    python scripts/migrate_crm_data.py \\
        --source $CRM_DATABASE_URL \\
        --target $YH_DATABASE_URL \\
        --execute

By default the script runs in DRY mode: it prints the rows it *would* insert,
counts per table, and exits without writing. Pass ``--execute`` to commit.

The script:
  1. Connects to both DBs (read-only on source).
  2. Ensures the ``crm_*`` tables exist on the target (assumes the consolidated
     yardharvest app has already booted at least once against the target DB so
     ``db.create_all()`` has run; if not, boot it first).
  3. For each source table, SELECTs all rows and INSERTs into the matching
     ``crm_*`` target table, preserving primary keys.
  4. Resets every Postgres sequence to ``MAX(id) + 1`` so subsequent inserts
     don't collide.

Idempotency: each table's target rows are deleted before inserting (only when
``--execute`` is set) so re-running the script gives the same end state.
Pass ``--no-truncate`` to append instead of replacing.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(2)


# (source_table, target_table, ordered_columns)
# Ordering matters: tables with FKs are inserted after their referenced tables.
TABLES: List[Tuple[str, str, List[str]]] = [
    ('user', 'crm_user', [
        'id', 'username', 'email', 'password_hash', 'role', 'created_at',
    ]),
    ('company', 'crm_company', [
        'id', 'name', 'city', 'state', 'org_type', 'website', 'tags',
        'fiscal_year_end', 'revenue', 'employees', 'billing_cycle',
    ]),
    ('contact', 'crm_contact', [
        'id', 'name', 'email', 'phone', 'image', 'email_opt_out', 'company_id',
    ]),
    ('email_template', 'crm_email_template', [
        'id', 'name', 'subject', 'body', 'created_at',
    ]),
    ('deal', 'crm_deal', [
        'id', 'title', 'amount', 'stage', 'contact_id', 'company_id',
        'owner_id', 'created_at', 'close_date', 'closed_reason',
        'last_activity_at', 'funding_source', 'grant_status',
        'budget_decision_date', 'rfp_due_date',
    ]),
    ('deal_contact', 'crm_deal_contact', [
        'id', 'deal_id', 'contact_id', 'role',
    ]),
    ('note', 'crm_note', [
        'id', 'content', 'contact_id', 'company_id', 'deal_id', 'created_at',
    ]),
    ('task', 'crm_task', [
        'id', 'title', 'due_date', 'done', 'priority', 'created_at',
        'contact_id', 'company_id', 'deal_id',
    ]),
    ('campaign', 'crm_campaign', [
        'id', 'name', 'subject', 'body', 'status', 'audience_desc',
        'created_at', 'sent_at', 'created_by',
    ]),
    ('campaign_recipient', 'crm_campaign_recipient', [
        'id', 'campaign_id', 'contact_id', 'status', 'created_at',
    ]),
    ('activity', 'crm_activity', [
        'id', 'kind', 'description', 'created_at', 'contact_id', 'company_id',
        'deal_id', 'user_id',
    ]),
]


def _normalize_pg_url(url: str) -> str:
    """Render hands out 'postgres://' but psycopg2 accepts both; normalize for clarity."""
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


def fetch_rows(conn, table: str, columns: List[str]):
    quoted_cols = ', '.join(f'"{c}"' for c in columns)
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f'SELECT {quoted_cols} FROM "{table}"')
        return cur.fetchall()


def insert_rows(conn, table: str, columns: List[str], rows, execute: bool):
    if not rows:
        return 0
    quoted_cols = ', '.join(f'"{c}"' for c in columns)
    placeholders = ', '.join(['%s'] * len(columns))
    sql = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders})'
    if not execute:
        return len(rows)
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur, sql, [[r[c] for c in columns] for r in rows], page_size=500,
        )
    return len(rows)


def truncate_target(conn, table: str, execute: bool):
    if not execute:
        return
    with conn.cursor() as cur:
        # CASCADE so FK-referencing rows in other crm_* tables also clear,
        # which matters if --no-truncate is omitted on a partial re-run.
        cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')


def reset_sequences(conn, execute: bool):
    """Bump each crm_* table's identity sequence past max(id)."""
    if not execute:
        return
    with conn.cursor() as cur:
        for _, target, _ in TABLES:
            cur.execute(f'''
                SELECT setval(
                    pg_get_serial_sequence('"{target}"', 'id'),
                    COALESCE((SELECT MAX(id) FROM "{target}"), 1),
                    true
                )
            ''')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=os.environ.get('CRM_SOURCE_DB_URL'),
                    help='Source DATABASE_URL (the standalone yardharvest-crm-db). '
                         'Falls back to the CRM_SOURCE_DB_URL env var so secrets '
                         'can be injected (e.g. from GitHub Actions) without '
                         'appearing on the command line.')
    ap.add_argument('--target', default=os.environ.get('CRM_TARGET_DB_URL'),
                    help='Target DATABASE_URL (yardharvest-db, post-consolidation). '
                         'Falls back to the CRM_TARGET_DB_URL env var.')
    ap.add_argument('--execute', action='store_true',
                    help='Actually write to the target. Default is dry-run.')
    ap.add_argument('--no-truncate', action='store_true',
                    help="Append to existing target rows instead of replacing.")
    args = ap.parse_args()

    if not args.source or not args.target:
        ap.error('source and target are required (pass --source/--target or set '
                 'CRM_SOURCE_DB_URL/CRM_TARGET_DB_URL).')

    src_url = _normalize_pg_url(args.source)
    tgt_url = _normalize_pg_url(args.target)

    print(f"Source : {src_url.split('@')[-1] if '@' in src_url else '???'}")
    print(f"Target : {tgt_url.split('@')[-1] if '@' in tgt_url else '???'}")
    print(f"Mode   : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"Trunc. : {'no (append)' if args.no_truncate else 'yes (replace)'}")
    print('-' * 60)

    src = psycopg2.connect(src_url)
    src.set_session(readonly=True)
    tgt = psycopg2.connect(tgt_url)

    try:
        total = 0
        # Truncate in REVERSE FK order so child rows clear before parents.
        if not args.no_truncate:
            for source_table, target_table, _ in reversed(TABLES):
                truncate_target(tgt, target_table, args.execute)
                print(f"  truncated {target_table}" if args.execute
                      else f"  would truncate {target_table}")
            print()

        # Insert in FK order.
        for source_table, target_table, cols in TABLES:
            rows = fetch_rows(src, source_table, cols)
            n = insert_rows(tgt, target_table, cols, rows, args.execute)
            total += n
            action = 'inserted' if args.execute else 'would insert'
            print(f"  {action:14} {n:5} rows  →  {target_table:25} "
                  f"(source: {source_table})")

        reset_sequences(tgt, args.execute)
        if args.execute:
            tgt.commit()
            print()
            print(f"Committed. Total rows migrated: {total}.")
        else:
            print()
            print(f"Dry-run complete. Total rows that *would* be inserted: {total}.")
            print("Re-run with --execute to commit.")
    except Exception:
        tgt.rollback()
        raise
    finally:
        src.close()
        tgt.close()


if __name__ == '__main__':
    main()
