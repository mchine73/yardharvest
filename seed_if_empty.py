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
    except Exception as e:
        db.session.rollback()
        listing_columns = []
        print(f"  Listing migration check skipped: {e}", flush=True)

    listing_migrations = {
        'image_url': 'VARCHAR(500)',
        'image_filename_2': 'VARCHAR(255)',
        'image_filename_3': 'VARCHAR(255)',
        'base_price': 'FLOAT',
        'initial_quantity': 'INTEGER',
        'price_floor': 'FLOAT',
        'price_ceiling': 'FLOAT',
        'smart_pricing_enabled': 'BOOLEAN DEFAULT TRUE',
    }
    for col_name, col_type in listing_migrations.items():
        if col_name not in listing_columns:
            safe_add_column('listing', col_name, col_type)

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

    # ── GardenPlot table: reservation columns ──
    try:
        gp_columns = [col['name'] for col in inspector.get_columns('garden_plot')]
    except Exception:
        db.session.rollback()
        gp_columns = []

    if 'reserved_by_id' not in gp_columns:
        safe_add_column('garden_plot', 'reserved_by_id', 'INTEGER')
    if 'reserved_at' not in gp_columns:
        safe_add_column('garden_plot', 'reserved_at', 'TIMESTAMP')

    # ── GardenWaitlist table: position column ──
    try:
        gw_columns = [col['name'] for col in inspector.get_columns('garden_waitlist')]
    except Exception:
        db.session.rollback()
        gw_columns = []

    if 'position' not in gw_columns:
        safe_add_column('garden_waitlist', 'position', 'INTEGER DEFAULT 0')

    # ── SharedResource table: time-based lending columns ──
    try:
        sr_columns = [col['name'] for col in inspector.get_columns('shared_resource')]
    except Exception:
        db.session.rollback()
        sr_columns = []

    if 'checkout_duration_days' not in sr_columns:
        safe_add_column('shared_resource', 'checkout_duration_days', 'INTEGER DEFAULT 3')
    if 'due_date' not in sr_columns:
        safe_add_column('shared_resource', 'due_date', 'TIMESTAMP')
    if 'qr_code_token' not in sr_columns:
        safe_add_column('shared_resource', 'qr_code_token', 'VARCHAR(64)')

    # ── CommunityGarden table: max checkouts per member ──
    try:
        cg_columns = [col['name'] for col in inspector.get_columns('community_garden')]
    except Exception:
        db.session.rollback()
        cg_columns = []

    if 'max_checkouts_per_member' not in cg_columns:
        safe_add_column('community_garden', 'max_checkouts_per_member', 'INTEGER DEFAULT 3')

    # ResourceCheckoutLog table created automatically by db.create_all()

    # ── SellerPlanting table: marketplace integration columns ──
    try:
        sp_columns = [col['name'] for col in inspector.get_columns('seller_planting')]
    except Exception:
        db.session.rollback()
        sp_columns = []

    if 'linked_listing_id' not in sp_columns:
        safe_add_column('seller_planting', 'linked_listing_id', 'INTEGER')
    if 'auto_list_on_harvest' not in sp_columns:
        safe_add_column('seller_planting', 'auto_list_on_harvest', 'BOOLEAN DEFAULT FALSE')

    # ── User table: SMS opt-in columns ──
    try:
        user_columns = [col['name'] for col in inspector.get_columns('user')]
    except Exception:
        db.session.rollback()
        user_columns = []

    if 'phone_number' not in user_columns:
        safe_add_column('user', 'phone_number', 'VARCHAR(20)')
    if 'sms_opt_in' not in user_columns:
        safe_add_column('user', 'sms_opt_in', 'BOOLEAN DEFAULT FALSE')

    # ── SiteEmailConfig table: SMS toggle columns ──
    try:
        sec_columns = [col['name'] for col in inspector.get_columns('site_email_config')]
    except Exception:
        db.session.rollback()
        sec_columns = []

    for sms_col in ['enable_sms_order_confirmation', 'enable_sms_status_updates', 'enable_sms_messages']:
        if sms_col not in sec_columns:
            safe_add_column('site_email_config', sms_col, 'BOOLEAN DEFAULT FALSE')

    if 'marketplace_enabled' not in sec_columns:
        safe_add_column('site_email_config', 'marketplace_enabled', 'BOOLEAN DEFAULT FALSE')

    # ── SiteEmailConfig table: harvest notification toggles ──
    for harvest_col in ['enable_harvest_notifications', 'enable_sms_harvest_notifications']:
        if harvest_col not in sec_columns:
            safe_add_column('site_email_config', harvest_col, 'BOOLEAN DEFAULT FALSE')

    # ── Order table: DoorDash delivery columns ──
    dd_order_migrations = {
        'doordash_delivery_id': 'VARCHAR(255)',
        'doordash_tracking_url': 'VARCHAR(500)',
        'delivery_provider': "VARCHAR(20) DEFAULT 'self'",
    }
    for col_name, col_type in dd_order_migrations.items():
        if col_name not in order_columns:
            safe_add_column('order', col_name, col_type)

    # ── PricingConfig table: DoorDash columns ──
    dd_pc_migrations = {
        'doordash_enabled': 'BOOLEAN DEFAULT FALSE',
        'doordash_subsidy_pct': 'FLOAT DEFAULT 0',
        'doordash_max_subsidy': 'FLOAT DEFAULT 5.0',
    }
    for col_name, col_type in dd_pc_migrations.items():
        if col_name not in pc_columns:
            safe_add_column('pricing_config', col_name, col_type)

    # ── Community Garden table: new columns for weather, grid ──
    try:
        cg_columns = [col.name for col in inspect(db.engine).get_columns('community_garden')]
    except Exception:
        db.session.rollback()
        cg_columns = []

    cg_migrations = {
        'latitude': 'FLOAT',
        'longitude': 'FLOAT',
        'weather_alerts_enabled': 'BOOLEAN DEFAULT FALSE',
        'grid_rows': 'INTEGER DEFAULT 4',
        'grid_cols': 'INTEGER DEFAULT 5',
    }
    for col_name, col_type in cg_migrations.items():
        if col_name not in cg_columns:
            safe_add_column('community_garden', col_name, col_type)

    # ── Garden Plot table: grid position & soil columns ──
    try:
        gp_columns = [col.name for col in inspect(db.engine).get_columns('garden_plot')]
    except Exception:
        db.session.rollback()
        gp_columns = []

    gp_migrations = {
        'grid_row': 'INTEGER',
        'grid_col': 'INTEGER',
        'soil_type': 'VARCHAR(30)',
        'sun_exposure': 'VARCHAR(20)',
        'custom_name': 'VARCHAR(100)',
    }
    for col_name, col_type in gp_migrations.items():
        if col_name not in gp_columns:
            safe_add_column('garden_plot', col_name, col_type)

    # ── Garden Email Config: sms_enabled ──
    try:
        gec_columns = [col.name for col in inspect(db.engine).get_columns('garden_email_config')]
    except Exception:
        db.session.rollback()
        gec_columns = []

    if 'sms_enabled' not in gec_columns:
        safe_add_column('garden_email_config', 'sms_enabled', 'BOOLEAN DEFAULT FALSE')

    # Mobile app: device push token columns
    try:
        result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user'"))
        user_columns = [r[0] for r in result]
    except Exception:
        db.session.rollback()
        user_columns = []

    if 'device_token' not in user_columns:
        safe_add_column('user', 'device_token', 'VARCHAR(255)')
    if 'device_platform' not in user_columns:
        safe_add_column('user', 'device_platform', 'VARCHAR(10)')

    # Create photo table if not exists
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS photo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES user(id),
                garden_id INTEGER REFERENCES community_garden(id),
                filename VARCHAR(255) NOT NULL,
                original_filename VARCHAR(255),
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                category VARCHAR(50) DEFAULT 'general',
                caption TEXT,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
        print("Ensured photo table exists", flush=True)
    except Exception as e:
        db.session.rollback()
        print(f"Photo table: {e}", flush=True)

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
