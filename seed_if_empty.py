"""Seed the database only if it's incomplete (safe for production deploys)."""
import sys
import traceback
from app import create_app, db
from app.models import User, Listing
from sqlalchemy import text, inspect

app = create_app()


def safe_add_column(table, col_name, col_type):
    """Add a column to a table, safely handling Postgres transaction errors."""
    try:
        # Quote table name to handle reserved words like "order"
        quoted_table = f'"{table}"' if table.lower() in ('order', 'user', 'group') else table
        db.session.execute(text(f'ALTER TABLE {quoted_table} ADD COLUMN {col_name} {col_type}'))
        db.session.commit()
        print(f"  Added {col_name} to {table}.", flush=True)
        return True
    except Exception as e:
        db.session.rollback()
        if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
            print(f"  {col_name} already exists on {table}, skipping.", flush=True)
        else:
            print(f"  Warning: could not add {col_name} to {table}: {e}", flush=True)
        return False


with app.app_context():
    db.create_all()

    # Add any missing columns to existing tables (db.create_all doesn't alter tables)
    # Use safe_add_column which handles Postgres transaction failures gracefully
    try:
        inspector = inspect(db.engine)
    except Exception:
        db.session.rollback()
        inspector = inspect(db.engine)

    # ── Listing table ──
    try:
        listing_columns = [col['name'] for col in inspector.get_columns('listing')]
        if 'image_url' not in listing_columns:
            print("Migrating listing table...", flush=True)
            safe_add_column('listing', 'image_url', 'VARCHAR(500)')
    except Exception as e:
        db.session.rollback()
        print(f"  Listing migration check skipped: {e}", flush=True)

    # ── Order table: economic model columns ──
    try:
        order_columns = [col['name'] for col in inspector.get_columns('order')]
    except Exception:
        db.session.rollback()
        order_columns = []

    order_migrations = {
        'subtotal': 'FLOAT DEFAULT 0',
        'delivery_fee': 'FLOAT DEFAULT 0',
        'platform_commission': 'FLOAT DEFAULT 0',
        'commission_rate': 'FLOAT DEFAULT 0',
        'seller_earnings': 'FLOAT DEFAULT 0',
    }
    for col_name, col_type in order_migrations.items():
        if col_name not in order_columns:
            safe_add_column('order', col_name, col_type)

    # ── PricingConfig table: platform economics columns ──
    try:
        pc_columns = [col['name'] for col in inspector.get_columns('pricing_config')]
    except Exception:
        db.session.rollback()
        pc_columns = []  # Table might not exist yet — db.create_all() will create it

    pc_migrations = {
        'commission_enabled': 'BOOLEAN DEFAULT TRUE',
        'delivery_fees_enabled': 'BOOLEAN DEFAULT TRUE',
        'per_mile_enabled': 'BOOLEAN DEFAULT FALSE',
        'free_delivery_enabled': 'BOOLEAN DEFAULT FALSE',
        'platform_commission_pct': 'FLOAT DEFAULT 0.08',
        'delivery_fee_flat': 'FLOAT DEFAULT 3.99',
        'delivery_fee_per_mile': 'FLOAT DEFAULT 0',
        'delivery_fee_free_threshold': 'FLOAT DEFAULT 0',
    }
    for col_name, col_type in pc_migrations.items():
        if col_name not in pc_columns:
            safe_add_column('pricing_config', col_name, col_type)

    # ── Order table: payment reference columns ──
    order_payment_migrations = {
        'payment_reference': 'VARCHAR(255)',
        'payment_status': 'VARCHAR(50)',
    }
    for col_name, col_type in order_payment_migrations.items():
        if col_name not in order_columns:
            safe_add_column('order', col_name, col_type)

    # ── SiteEmailConfig + GardenEmailConfig tables ──
    # db.create_all() handles new table creation, but log for visibility
    try:
        inspector.get_columns('site_email_config')
        print("  SiteEmailConfig table exists.", flush=True)
    except Exception:
        db.session.rollback()
        print("  SiteEmailConfig table will be created by db.create_all().", flush=True)

    try:
        inspector.get_columns('garden_email_config')
        print("  GardenEmailConfig table exists.", flush=True)
    except Exception:
        db.session.rollback()
        print("  GardenEmailConfig table will be created by db.create_all().", flush=True)

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
