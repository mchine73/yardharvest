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
    ('pricing_config', 'garden_pro_enabled', 'BOOLEAN', 'TRUE'),
    ('pricing_config', 'garden_pro_trial_days', 'INTEGER', '14'),
    ('pricing_config', 'garden_pro_monthly_cents', 'INTEGER', '1500'),
    ('pricing_config', 'garden_pro_yearly_cents', 'INTEGER', '12500'),
    # Stripe integration columns
    ('user', 'stripe_customer_id', 'VARCHAR(255)', 'NULL'),
    ('user', 'stripe_connect_account_id', 'VARCHAR(255)', 'NULL'),
    ('user', 'stripe_onboarding_complete', 'BOOLEAN', 'FALSE'),
    ('"order"', 'stripe_payment_intent_id', 'VARCHAR(255)', 'NULL'),
    ('seller_payout', 'stripe_transfer_id', 'VARCHAR(255)', 'NULL'),
    ('garden_subscription', 'stripe_subscription_id', 'VARCHAR(255)', 'NULL'),
    # Refund + promo columns on Order
    ('"order"', 'refund_status', 'VARCHAR(20)', 'NULL'),
    ('"order"', 'refund_amount', 'FLOAT', '0'),
    ('"order"', 'discount_amount', 'FLOAT', '0'),
    ('"order"', 'promo_code_id', 'INTEGER', 'NULL'),
]


def run():
    with app.app_context():
        inspector = inspect(db.engine)

        for table, column, sql_type, default in MIGRATIONS:
            try:
                # Strip quotes for inspector lookup
                bare_table = table.strip('"')
                existing = [c['name'] for c in inspector.get_columns(bare_table)]
            except Exception:
                db.session.rollback()
                existing = []

            if column in existing:
                print(f'  [SKIP] {table}.{column} already exists')
                continue

            # Quote table name to handle PostgreSQL reserved words (user, order, group)
            # Some entries already have quotes (e.g. '"order"'), skip double-quoting
            quoted_table = table if table.startswith('"') else f'"{table}"'
            sql = f'ALTER TABLE {quoted_table} ADD COLUMN {column} {sql_type} DEFAULT {default}'
            try:
                db.session.execute(text(sql))
                db.session.commit()
                print(f'  [OK]   {table}.{column} added')
            except Exception as e:
                db.session.rollback()
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    print(f'  [SKIP] {table}.{column} already exists')
                else:
                    print(f'  [WARN] {table}.{column} failed: {e}')

        # db.create_all() handles new tables like garden_subscription
        db.create_all()
        print('  [OK]   New tables created (if any)')
        print('\nMigration complete.')


if __name__ == '__main__':
    run()
