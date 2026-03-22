"""Add Refund, PromoCode, PromoCodeUsage tables and Order refund/discount columns."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

app = create_app()

# New columns on existing Order table
ORDER_COLUMNS = [
    ('"order"', 'refund_status', 'VARCHAR(20)'),
    ('"order"', 'refund_amount', 'FLOAT DEFAULT 0'),
    ('"order"', 'discount_amount', 'FLOAT DEFAULT 0'),
    ('"order"', 'promo_code_id', 'INTEGER'),
]

# New tables
CREATE_TABLES = [
    '''CREATE TABLE IF NOT EXISTS refund (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES "order"(id),
        garden_subscription_id INTEGER REFERENCES garden_subscription(id),
        refund_type VARCHAR(20) NOT NULL,
        amount FLOAT NOT NULL,
        reason TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        stripe_refund_id VARCHAR(255),
        stripe_reversal_id VARCHAR(255),
        initiated_by_id INTEGER NOT NULL REFERENCES "user"(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS promo_code (
        id SERIAL PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        description VARCHAR(255),
        discount_type VARCHAR(20) NOT NULL,
        discount_value FLOAT NOT NULL,
        scope VARCHAR(20) DEFAULT 'both',
        max_uses INTEGER,
        current_uses INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_by_id INTEGER NOT NULL REFERENCES "user"(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS promo_code_usage (
        id SERIAL PRIMARY KEY,
        promo_code_id INTEGER NOT NULL REFERENCES promo_code(id),
        user_id INTEGER NOT NULL REFERENCES "user"(id),
        order_id INTEGER REFERENCES "order"(id),
        garden_subscription_id INTEGER REFERENCES garden_subscription(id),
        discount_applied FLOAT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
]

with app.app_context():
    for table, column, col_type in ORDER_COLUMNS:
        try:
            db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
            db.session.commit()
            print(f'  Added {table}.{column}')
        except Exception as e:
            db.session.rollback()
            if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                print(f'  {table}.{column} already exists')
            else:
                print(f'  {table}.{column} error: {e}')

    for sql in CREATE_TABLES:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            table_name = sql.split('CREATE TABLE IF NOT EXISTS ')[1].split(' (')[0]
            print(f'  Created table {table_name}')
        except Exception as e:
            db.session.rollback()
            print(f'  Table error: {e}')

    print('Migration complete.')
