#!/usr/bin/env python3
"""Ensure the production admin user from Render env vars on the production database.

This script is intended for the Render startup path only.
It must not be treated as a local admin reset flow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash


def _prepare_import_path() -> None:
    this_file = Path(__file__).resolve()
    backend_dir = this_file.parents[1]
    repo_root = backend_dir.parent
    for path in (str(repo_root), str(backend_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _prepare_import_path()

    username = (os.getenv("ADMIN_SEED_USERNAME") or "").strip()
    email = (os.getenv("ADMIN_SEED_EMAIL") or "").strip()
    password = os.getenv("ADMIN_SEED_PASSWORD") or ""
    role = (os.getenv("ADMIN_SEED_ROLE") or "superadmin").strip() or "superadmin"

    if not username or not email or not password:
        print(
            "[HC] ensure_render_admin: skipped production bootstrap "
            "(missing ADMIN_SEED_USERNAME/ADMIN_SEED_EMAIL/ADMIN_SEED_PASSWORD)"
        )
        return 0

    from sqlalchemy import or_

    from run import app
    from backend.extensions import db
    from backend.models import AdminUser

    with app.app_context():
        print("[HC] TARGET_ENV=production")
        print("[HC] TARGET_SCOPE=Render/Neon production admin bootstrap only")
        print("[HC] LOCAL_NOTE=does not affect any local SQLite admin credentials")
        inspector = db.inspect(db.engine)
        if "admin_users" not in inspector.get_table_names():
            print("[HC] ensure_render_admin: skipped production bootstrap (admin_users table not available yet)")
            return 0

        admin = (
            db.session.query(AdminUser)
            .filter(
                or_(
                    db.func.lower(AdminUser.username) == username.lower(),
                    db.func.lower(AdminUser.email) == email.lower(),
                )
            )
            .order_by(AdminUser.id.asc())
            .first()
        )

        password_hash = generate_password_hash(password)

        if admin is None:
            admin = AdminUser(
                username=username,
                email=email,
                role=role,
                is_active=True,
            )
            admin.password_hash = password_hash
            db.session.add(admin)
            db.session.commit()
            print(f"[HC] ensure_render_admin: created production admin id={admin.id}")
            return 0

        admin.username = username
        admin.email = email
        admin.password_hash = password_hash
        admin.is_active = True
        admin.role = role
        db.session.commit()
        print(f"[HC] ensure_render_admin: updated production admin id={admin.id}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
