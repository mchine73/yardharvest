"""One-time migration: add new columns to existing tables.

Run this once in production after deploying the new models:
  python migrate_new_columns.py

Safe to run multiple times — checks if columns exist before adding.
db.create_all() handles new tables (GardenSubscription) automatically,
but cannot add columns to existing tables.
"""
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

MIGRATIONS = [
    # (table, column, sql_type, default)
    ('user', 'token_version', 'INTEGER', '0'),
    ('community_garden', 'subscription_status', "VARCHAR(20)", "'none'"),
]


def run():
    with app.app_context():
        inspector = inspect(db.engine)

        for table, column, sql_type, default in MIGRATIONS:
            existing = [c['name'] for c in inspector.get_columns(table)]
            if column in existing:
                print(f'  [SKIP] {table}.{column} already exists')
                continue

            sql = f'ALTER TABLE {table} ADD COLUMN {column} {sql_type} DEFAULT {default}'
            db.session.execute(text(sql))
            db.session.commit()
            print(f'  [OK]   {table}.{column} added')

        # db.create_all() handles new tables like garden_subscription
        db.create_all()
        print('  [OK]   New tables created (if any)')
        print('\nMigration complete.')


if __name__ == '__main__':
    run()
