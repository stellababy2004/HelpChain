"""Delete a User row by username (safe, idempotent).

Usage:
  # Dry-run (default)
  python backend/scripts/delete_user.py --username admin

  # To actually delete
  python backend/scripts/delete_user.py --username admin --commit

This script requires you run it from the repository root. It will import
the Flask app and perform the deletion inside the app context.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

# Ensure repo root and backend dir are on sys.path when running directly
_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_backend_dir = os.path.join(_repo_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete a User by username")
    parser.add_argument("--username", required=True, help="username to delete")
    parser.add_argument("--commit", action="store_true", help="Apply deletion (default dry-run)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    dry_run = not args.commit

    try:
        from app import User, app, db
    except Exception as e:
        logging.error("Failed to import app/models: %s", e)
        return 2

    with app.app_context():
        try:
            user = User.query.filter_by(username=args.username).first()
        except Exception as e:
            logging.exception("DB query failed: %s", e)
            return 3

        if not user:
            logging.info("No User with username '%s' found.", args.username)
            return 0

        logging.info("Found User: id=%s username=%s email=%s", getattr(user, "id", "?"), getattr(user, "username", ""), getattr(user, "email", ""))
        if dry_run:
            logging.info("Dry-run: would delete this User. Re-run with --commit to apply.")
            return 0

        try:
            db.session.delete(user)
            db.session.commit()
            logging.info("Deleted User '%s'", args.username)
            return 0
        except Exception:
            db.session.rollback()
            logging.exception("Failed to delete User '%s'", args.username)
            return 4


if __name__ == "__main__":
    raise SystemExit(main())
