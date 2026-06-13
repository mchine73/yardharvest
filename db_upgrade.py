"""Apply database migrations on deploy (Alembic via Flask-Migrate).

Run once per deploy from build.sh, before the app starts. Handles three cases
so the cutover from the old db.create_all()+hand-rolled-column-scripts approach
is safe even on the live production database:

  1. Fresh database (no tables)            -> `upgrade head`: the baseline
     migration builds the entire schema.
  2. Pre-Alembic database (tables present, -> `stamp head`: records the baseline
     but no alembic_version table)            revision WITHOUT running any DDL,
     so the existing production schema is never altered. The next deploy then
     upgrades normally.
  3. Already on Alembic (alembic_version)  -> `upgrade head`: apply any new
     migrations.

Idempotent and safe to re-run.
"""
import logging

from flask import current_app
from sqlalchemy import inspect
from alembic.script import ScriptDirectory
from flask_migrate import upgrade, stamp

from app import create_app, db

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('db_upgrade')

app = create_app()

with app.app_context():
    tables = set(inspect(db.engine).get_table_names())
    if 'alembic_version' in tables:
        log.info('[db_upgrade] Alembic present -> upgrade head')
        upgrade()
    elif 'user' in tables:
        # Pre-Alembic production DB: its schema matches the BASELINE migration,
        # but there's no alembic_version row. Stamp the baseline revision (NOT
        # head) so we record only what's actually built — stamping head would
        # mark every later migration as applied without running its DDL,
        # silently skipping schema changes. Then upgrade to apply anything newer
        # than the baseline in the same run.
        cfg = current_app.extensions['migrate'].migrate.get_config()
        baseline = ScriptDirectory.from_config(cfg).get_bases()[0]
        log.info('[db_upgrade] Pre-Alembic database -> stamp baseline %s, then upgrade head', baseline)
        stamp(revision=baseline)
        upgrade()
    else:
        log.info('[db_upgrade] Fresh database -> upgrade head')
        upgrade()
    log.info('[db_upgrade] Done.')
