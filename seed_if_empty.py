"""Seed the database only if it's incomplete (safe for production deploys)."""
import sys
import traceback
from app import create_app, db
from app.models import User, Listing
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    db.create_all()

    # Add any missing columns to existing tables (db.create_all doesn't alter tables)
    inspector = inspect(db.engine)
    listing_columns = [col['name'] for col in inspector.get_columns('listing')]

    if 'image_url' not in listing_columns:
        print("Adding image_url column to listing table...", flush=True)
        db.session.execute(text('ALTER TABLE listing ADD COLUMN image_url VARCHAR(500)'))
        db.session.commit()
        print("Column added successfully.", flush=True)

    # Add economic model columns to Order table
    order_columns = [col['name'] for col in inspector.get_columns('order')]
    new_order_cols = {
        'subtotal': 'FLOAT DEFAULT 0',
        'delivery_fee': 'FLOAT DEFAULT 0',
        'platform_commission': 'FLOAT DEFAULT 0',
        'commission_rate': 'FLOAT DEFAULT 0',
        'seller_earnings': 'FLOAT DEFAULT 0',
    }
    for col_name, col_type in new_order_cols.items():
        if col_name not in order_columns:
            print(f"Adding {col_name} column to order table...", flush=True)
            db.session.execute(text(f'ALTER TABLE "order" ADD COLUMN {col_name} {col_type}'))
    if any(c not in order_columns for c in new_order_cols):
        db.session.commit()
        print("Order economic columns added.", flush=True)

    # Add platform economics columns to pricing_config table
    try:
        pc_columns = [col['name'] for col in inspector.get_columns('pricing_config')]
        new_pc_cols = {
            'commission_enabled': 'BOOLEAN DEFAULT 1',
            'delivery_fees_enabled': 'BOOLEAN DEFAULT 1',
            'per_mile_enabled': 'BOOLEAN DEFAULT 0',
            'free_delivery_enabled': 'BOOLEAN DEFAULT 0',
            'platform_commission_pct': 'FLOAT DEFAULT 0.08',
            'delivery_fee_flat': 'FLOAT DEFAULT 3.99',
            'delivery_fee_per_mile': 'FLOAT DEFAULT 0',
            'delivery_fee_free_threshold': 'FLOAT DEFAULT 0',
        }
        for col_name, col_type in new_pc_cols.items():
            if col_name not in pc_columns:
                print(f"Adding {col_name} column to pricing_config table...", flush=True)
                db.session.execute(text(f'ALTER TABLE pricing_config ADD COLUMN {col_name} {col_type}'))
        if any(c not in pc_columns for c in new_pc_cols):
            db.session.commit()
            print("PricingConfig economic columns added.", flush=True)
    except Exception:
        pass  # Table might not exist yet — db.create_all() will create it

    user_count = User.query.count()
    listing_count = Listing.query.count()
    print(f"DB check: {user_count} users, {listing_count} listings", flush=True)

    if user_count < 8 or listing_count < 18:
        print("Database incomplete — seeding now...", flush=True)
        try:
            from seed import seed
            seed()
            print("Seeding complete!", flush=True)
        except Exception as e:
            print(f"SEED ERROR: {e}", flush=True)
            traceback.print_exc()
            # Don't exit with error - let gunicorn start anyway
            print("Seeding failed but continuing startup...", flush=True)
    else:
        print("Database already fully seeded — skipping.", flush=True)
