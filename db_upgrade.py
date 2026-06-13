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

from sqlalchemy import inspect
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
        # Pre-Alembic production DB: adopt the baseline without touching schema.
        log.info('[db_upgrade] Existing pre-Alembic database -> stamp head (no DDL)')
        stamp()
    else:
        log.info('[db_upgrade] Fresh database -> upgrade head')
        upgrade()
    log.info('[db_upgrade] Done.')
