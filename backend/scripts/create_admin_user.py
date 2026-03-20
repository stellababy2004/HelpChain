from __future__ import annotations

import getpass
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.models import AdminUser, Structure, get_default_structure
from backend.extensions import db


def main() -> int:
    app = create_app()
    with app.app_context():
        email = input("Admin email: ").strip()
        username = input("Username (default admin): ").strip() or "admin"
        password = getpass.getpass("Password (must include upper/lower/digit): ").strip()

        if not email or not password:
            print("Email and password are required.")
            return 1

        existing = AdminUser.query.filter(
            (AdminUser.email == email) | (AdminUser.username == username)
        ).first()
        if existing:
            print("Admin user already exists.")
            return 1

        structure = get_default_structure()
        if not structure:
            structure = Structure(name="Default", slug="default", status="active")
            db.session.add(structure)
            db.session.flush()

        admin = AdminUser(
            username=username,
            email=email,
            role="admin",
            is_active=True,
            structure_id=structure.id,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Created admin user id={admin.id} for structure_id={structure.id}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
