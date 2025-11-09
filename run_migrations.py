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

# Ensure stdout/stderr use UTF-8 so any module-level prints with
# non-ASCII text don't raise UnicodeEncodeError on Windows runners
# (some modules print localized strings at import time).
try:
    # Python 3.7+: reconfigure std streams to UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    # Fallback: set PYTHONIOENCODING for subprocesses/readers
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Import and create app
from backend.appy import app


def run_migrations():
    """Run database migrations"""
    with app.app_context():
        try:
            # Import the migrate command from alembic
            from alembic.command import upgrade
            from alembic.config import Config

            # Create alembic config pointing to the project's alembic.ini so
            # env.py can read logging configuration and script_location.
            alembic_ini = os.path.join(
                os.path.dirname(__file__), "backend", "migrations", "alembic.ini"
            )
            alembic_cfg = Config(alembic_ini)

            # Ensure script_location points to the migrations directory (absolute)
            script_loc = os.path.join(
                os.path.dirname(__file__), "backend", "migrations"
            )
            alembic_cfg.set_main_option("script_location", script_loc)

            # If CI/job provided DATABASE_URL, ensure alembic uses it.
            db_url = os.environ.get("DATABASE_URL")
            if db_url:
                alembic_cfg.set_main_option("sqlalchemy.url", db_url)

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
