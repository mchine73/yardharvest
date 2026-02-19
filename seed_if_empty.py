"""Seed the database only if it's empty (safe for production deploys)."""
import subprocess
import sys
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    if User.query.first() is None:
        print("Database is empty — seeding now...")
        result = subprocess.run(
            [sys.executable, 'seed.py'],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"Seed error: {result.stderr}")
            sys.exit(1)
        print("Seeding complete!")
    else:
        print("Database already has data — skipping seed.")
