from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import inspect, or_

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.local_db_guard import (
    APP_IMPORT_PATH,
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)

ADMIN_EMAIL = "contact@helpchain.live"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ROLE = "superadmin"

if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD environment variable is required for reset_admin_local.py"
    )
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset local admin user on canonical DB only")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow DB write",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        from backend.appy import app
        from backend.models import AdminUser, db
    except Exception as exc:
        print(f"ERROR: failed to import app/models ({APP_IMPORT_PATH}): {exc}")
        return 1

    try:
        with app.app_context():
            uri = app.config.get("SQLALCHEMY_DATABASE_URI")
            print_app_db_preflight(uri)
            if not args.confirm_canonical_db:
                print(canonical_confirmation_error())
                return 2
            if not is_canonical_db_uri(uri):
                print(canonical_mismatch_error(uri))
                return 2

            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            if "admin_users" not in tables:
                print("ERROR: required table missing: admin_users")
                print(
                    "HINT: verify local DB target and run migrations on the same app entrypoint/database."
                )
                return 1

            user = (
                AdminUser.query.filter(
                    or_(
                        AdminUser.username == ADMIN_USERNAME,
                        AdminUser.email == ADMIN_EMAIL,
                    )
                )
                .order_by(AdminUser.id.asc())
                .first()
            )

            changed = False
            action = ""

            if user is None:
                user = AdminUser(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    role=ADMIN_ROLE,
                    is_active=True,
                )
                if not hasattr(user, "set_password"):
                    print("ERROR: AdminUser.set_password() is missing; cannot reset password safely.")
                    return 1
                user.set_password(ADMIN_PASSWORD)
                db.session.add(user)
                changed = True
                action = "created"
            else:
                updates = {
                    "username": ADMIN_USERNAME,
                    "email": ADMIN_EMAIL,
                    "role": ADMIN_ROLE,
                    "is_active": True,
                }
                for field, value in updates.items():
                    if getattr(user, field, None) != value:
                        setattr(user, field, value)
                        changed = True

                try:
                    has_password = bool(
                        user.check_password(ADMIN_PASSWORD)
                        if hasattr(user, "check_password")
                        else False
                    )
                except Exception:
                    has_password = False
                if not has_password:
                    if not hasattr(user, "set_password"):
                        print(
                            "ERROR: AdminUser.set_password() is missing; cannot reset password safely."
                        )
                        return 1
                    user.set_password(ADMIN_PASSWORD)
                    changed = True

                action = "updated"

            if changed:
                db.session.commit()
                print(
                    f"OK: admin {action} (id={user.id}, username={user.username}, email={user.email}, role={user.role})"
                )
            else:
                print(
                    f"OK: no changes needed (id={user.id}, username={user.username}, email={user.email}, role={user.role})"
                )
    except Exception as exc:
        print(f"ERROR: admin reset failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
