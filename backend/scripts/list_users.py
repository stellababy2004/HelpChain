"""List usernames from the User table using the app context.

Run from repository root:
  python backend/scripts/list_users.py
"""
from __future__ import annotations

import sys
import os

# Ensure backend package is importable when running this script from repo root
_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_backend_dir = os.path.join(_repo_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

try:
    from app import app, User, db
except Exception as e:
    print("Failed importing backend app:", e)
    raise


def main() -> int:
    try:
        with app.app_context():
            # Show DB engine info for diagnostics
            try:
                engine_name = getattr(db.engine, "name", "unknown")
                print(f"DB engine: {engine_name}")
            except Exception:
                pass

            users = User.query.order_by(User.id).all()
            if not users:
                print("No users found (empty result).")
            else:
                print(f"Found {len(users)} users:")
                for u in users:
                    print(
                        f" - {getattr(u, 'id', '?')}: {getattr(u, 'username', '')} <{getattr(u, 'email', '')}>"
                    )
    except Exception as exc:
        print("Error querying users:", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
