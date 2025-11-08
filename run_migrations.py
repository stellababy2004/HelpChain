#!/usr/bin/env python3
"""
Simple script to run database migrations
"""

import os
import sys

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

# Set environment variables
os.environ.setdefault("FLASK_ENV", "development")

# Import and create app
from backend.appy import app


def run_migrations():
    """Run database migrations"""
    with app.app_context():
        try:
            # Import the migrate command from flask_migrate
            from alembic.command import upgrade
            from alembic.config import Config

            # Create alembic config
            alembic_cfg = Config("alembic.ini")

            print("Running database migrations...")
            upgrade(alembic_cfg, "head")
            print("✅ Database migrations completed successfully!")
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback

            traceback.print_exc()
            return False
    return True


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
