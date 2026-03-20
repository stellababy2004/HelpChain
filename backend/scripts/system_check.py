from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import AdminUser


def main() -> int:
    app = create_app()
    with app.app_context():
        print("=== System Check ===")
        print(f"SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        print(f"SECRET_KEY set: {bool(app.config.get('SECRET_KEY'))}")
        print(f"SESSION_COOKIE_NAME: {app.config.get('SESSION_COOKIE_NAME')}")

        # Routes
        rules = {r.rule for r in app.url_map.iter_rules()}
        required = {"/admin/login", "/admin/ops/login", "/admin", "/admin/", "/admin/command"}
        print("Routes present:")
        for r in sorted(required):
            print(f"  {r}: {'OK' if r in rules else 'MISSING'}")

        # Tables
        bind = db.session.get_bind()
        inspector = inspect(bind)
        tables = set(inspector.get_table_names())
        print("Tables present (subset):")
        for name in ["admin_users", "users", "structures", "cases", "case_events", "alembic_version"]:
            print(f"  {name}: {'OK' if name in tables else 'MISSING'}")

        # Admin user
        if "admin_users" in tables:
            admin_count = AdminUser.query.count()
            print(f"Admin users: {admin_count} {'OK' if admin_count > 0 else 'MISSING'}")
        else:
            print("Admin users: MISSING (table missing)")

        # Alembic version
        if "alembic_version" in tables:
            version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"Alembic version: {version}")
        else:
            print("Alembic version: table missing")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
