"""Seed the database only if it's empty (safe for production deploys)."""
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    if User.query.first() is None:
        print("Database is empty — seeding...")
        from seed import seed
        seed()
    else:
        print("Database already has data — skipping seed.")
