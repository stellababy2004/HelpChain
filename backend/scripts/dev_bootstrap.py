# Run this once to initialize development database
# This script runs migrations and creates the default admin.
from __future__ import annotations

import pathlib
import sys

from sqlalchemy import inspect

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import AdminUser, Structure, get_default_structure


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "943415StoyanovaNova!"
DEFAULT_ADMIN_ROLE = "superadmin"


def _ensure_tables_exist() -> bool:
    bind = db.session.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    required = {"users", "admin_users", "structures", "cases", "case_events"}
    missing = sorted(required - tables)
    if missing:
        print(f"Missing tables: {', '.join(missing)}")
        return False
    return True


def main() -> int:
    app = create_app()
    with app.app_context():
        try:
            from flask_migrate import upgrade
        except Exception as exc:
            print(f"Flask-Migrate not available: {exc}")
            return 1

        print("Running migrations...")
        upgrade()

        if not _ensure_tables_exist():
            print("Database not initialized. Run migrations.")
            return 1

        structure = get_default_structure()
        if not structure:
            structure = Structure(name="Default", slug="default", status="active")
            db.session.add(structure)
            db.session.commit()
            print("Created default structure.")

        admin = AdminUser.query.first()
        if not admin:
            admin = AdminUser(
                username=DEFAULT_ADMIN_USERNAME,
                email="admin@localhost",
                role=DEFAULT_ADMIN_ROLE,
                is_active=True,
                structure_id=structure.id,
            )
            admin.set_password(DEFAULT_ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print("Created default admin user.")
        else:
            print("Admin user already exists.")

    print("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
