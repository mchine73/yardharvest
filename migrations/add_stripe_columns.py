"""Add Stripe integration columns to existing tables."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

app = create_app()

COLUMNS = [
    ('user', 'stripe_customer_id', 'VARCHAR(255)'),
    ('user', 'stripe_connect_account_id', 'VARCHAR(255)'),
    ('user', 'stripe_onboarding_complete', 'BOOLEAN DEFAULT FALSE'),
    ('"order"', 'stripe_payment_intent_id', 'VARCHAR(255)'),
    ('seller_payout', 'stripe_transfer_id', 'VARCHAR(255)'),
    ('garden_subscription', 'stripe_subscription_id', 'VARCHAR(255)'),
]

with app.app_context():
    for table, column, col_type in COLUMNS:
        try:
            db.session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'
            ))
            db.session.commit()
            print(f'  Added {table}.{column}')
        except Exception as e:
            db.session.rollback()
            if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                print(f'  {table}.{column} already exists — skipping')
            else:
                print(f'  {table}.{column} error: {e}')

    print('Migration complete.')
