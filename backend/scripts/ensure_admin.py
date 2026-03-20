#!/usr/bin/env python3
"""
Idempotent admin bootstrap for DB-backed admin login.

Behavior:
- If ADMIN_SEED_USERNAME or ADMIN_SEED_PASSWORD is missing, exits with no-op.
- If admin user does not exist, creates it with a hashed password.
- If admin user exists:
  - ADMIN_SEED_FORCE_RESET=1 -> reset password (and update email if provided)
  - otherwise no-op.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import argparse


def _prepare_import_path() -> None:
    # Support both:
    # - `python backend/scripts/ensure_admin.py` (repo root cwd)
    # - `python scripts/ensure_admin.py` (backend cwd)
    this_file = Path(__file__).resolve()
    backend_dir = this_file.parents[1]
    repo_root = backend_dir.parent
    for p in (str(repo_root), str(backend_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    _prepare_import_path()
    parser = argparse.ArgumentParser(
        description="Ensure admin user on the effective local runtime DB"
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow DB write to the effective local runtime DB",
    )
    args = parser.parse_args()

    username = (os.getenv("ADMIN_SEED_USERNAME") or "").strip()
    password = os.getenv("ADMIN_SEED_PASSWORD") or ""
    email = (os.getenv("ADMIN_SEED_EMAIL") or "").strip()
    role = (os.getenv("ADMIN_SEED_ROLE") or "superadmin").strip().lower()
    force_reset = _env_truthy(os.getenv("ADMIN_SEED_FORCE_RESET"))

    if not username or not password:
        print(
            "ENSURE_ADMIN: skip (missing ADMIN_SEED_USERNAME or ADMIN_SEED_PASSWORD)"
        )
        return 0

    allowed_roles = {"superadmin", "ops", "readonly", "admin", "super_admin"}
    if role not in allowed_roles:
        print(
            "ENSURE_ADMIN: error (ADMIN_SEED_ROLE must be one of "
            "superadmin|ops|readonly|admin|super_admin)"
        )
        return 1

    from backend.extensions import db
    from backend.local_db_guard import (
        runtime_confirmation_error,
        runtime_mismatch_error,
        select_local_runtime_db,
        print_app_db_preflight,
        normalize_uri,
    )
    from backend.models import AdminUser

    from backend.appy import app

    selection = select_local_runtime_db()
    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        print(f"EFFECTIVE LOCAL DB: {selection.selected_uri}")
        if not args.confirm_canonical_db:
            print(runtime_confirmation_error())
            return 2
        if not selection.selected_uri:
            print("ENSURE_ADMIN: error (local runtime DB selection unavailable)")
            return 2
        if normalize_uri(runtime_uri) != normalize_uri(selection.selected_uri):
            print(runtime_mismatch_error(runtime_uri, selection.selected_uri))
            return 2

        existing = db.session.query(AdminUser).filter_by(username=username).first()
        if existing:
            if not force_reset:
                print("ENSURE_ADMIN: exists (no-op)")
                return 0

            if len(password) < 12:
                print(
                    "ENSURE_ADMIN: error (ADMIN_SEED_FORCE_RESET=1 requires password length >= 12)"
                )
                return 1

            try:
                existing.set_password(password)
            except Exception as exc:
                print(f"ENSURE_ADMIN: error (invalid ADMIN_SEED_PASSWORD: {exc})")
                return 1

            if email:
                existing.email = email
            db.session.commit()

            # Best-effort audit entry for forced resets.
            try:
                from backend.audit import log_activity

                log_activity(
                    entity_type="admin",
                    entity_id=getattr(existing, "id", 0) or 0,
                    action="admin_seed_reset",
                    message="Admin password reset via ensure_admin (forced)",
                    meta={"username": username, "forced": True},
                    persist=True,
                )
            except Exception:
                pass

            print("ENSURE_ADMIN: reset password (forced)")
            return 0

        create_email = email or "admin@helpchain.live"
        admin = AdminUser(username=username, email=create_email, role=role)
        try:
            admin.set_password(password)
        except Exception as exc:
            print(f"ENSURE_ADMIN: error (invalid ADMIN_SEED_PASSWORD: {exc})")
            return 1

        db.session.add(admin)
        db.session.commit()
        print("ENSURE_ADMIN: created")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
