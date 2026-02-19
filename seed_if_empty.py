"""Seed the database only if it's empty (safe for production deploys)."""
import sys
import traceback
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    if User.query.first() is None:
        print("Database is empty — seeding now...", flush=True)
        try:
            from seed import seed
            seed()
            print("Seeding complete!", flush=True)
        except Exception as e:
            print(f"SEED ERROR: {e}", flush=True)
            traceback.print_exc()
            sys.exit(1)
    else:
        print("Database already has data — skipping seed.", flush=True)
