"""Seed the database only if it's incomplete (safe for production deploys)."""
import sys
import traceback
from app import create_app, db
from app.models import User, Listing

app = create_app()

with app.app_context():
    db.create_all()
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
