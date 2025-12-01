"""Sync AdminUser rows into the User table.

Safe, idempotent script intended to be run from the repository root.

Usage (PowerShell):
  python backend/scripts/sync_admin_to_users.py --dry-run
  python backend/scripts/sync_admin_to_users.py --commit

The script will, for each `AdminUser` row, ensure there is a corresponding
`User` row with the same `username` (creates if missing). It will not
overwrite existing user passwords. By default it runs as a dry-run.
"""
from __future__ import annotations

import argparse
import logging
import secrets
import sys
from typing import Optional
import os


# Ensure repository root (parent of `backend`) is on sys.path so
# `import backend` works when the script is executed directly as
# `python backend/scripts/sync_admin_to_users.py` (Python sets sys.path[0]
# to the script directory, which would otherwise shadow the package root).
try:
    _this_dir = os.path.abspath(os.path.dirname(__file__))
    _repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    # Also ensure the `backend/` package directory is on sys.path so modules
    # that rely on top-level imports like `import dependencies` succeed when
    # running this script directly from the repository root.
    try:
        _backend_dir = os.path.abspath(os.path.join(_repo_root, "backend"))
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)
    except Exception:
        pass
except Exception:
    # If anything goes wrong here, continue and let the later import fail
    pass


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync AdminUser rows into the User table (idempotent)."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Apply changes to the database (default is dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly run as a dry-run (no DB changes).",
    )
    parser.add_argument(
        "--password",
        help="Optional fixed password to set for any created users.",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path to append created usernames and passwords (only written on --commit).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Determine dry-run / commit precedence: --commit wins if provided.
    if args.commit and args.dry_run:
        logging.warning("Both --commit and --dry-run provided; --commit takes precedence")
    if args.commit:
        dry_run = False
    elif args.dry_run:
        dry_run = True
    else:
        # Default behaviour: dry-run
        dry_run = True

    # Import app and models via the project entrypoint so sys.path is set like normal
    try:
        # `run.py` and other dev helpers add `backend/` to sys.path; we import app
        from backend.app import app, db, AdminUser, User
    except Exception as e:  # pragma: no cover - defensive import failure
        logging.error("Failed to import app/models: %s", e)
        return 2

    created = 0
    updated = 0
    skipped = 0
    log_file_path = args.log_file
    fixed_password = args.password

    with app.app_context():
        try:
            admins = AdminUser.query.all()
        except Exception as e:  # pragma: no cover - DB query failure
            logging.error("Failed to query AdminUser: %s", e)
            return 3

        if not admins:
            logging.info("No AdminUser rows found. Nothing to do.")
            return 0

        for au in admins:
            # Defensive attribute access
            username = getattr(au, "username", None)
            email = getattr(au, "email", None)
            if not username:
                logging.warning("Skipping AdminUser with missing username (id=%s)", getattr(au, "id", "?"))
                skipped += 1
                continue

            try:
                existing = User.query.filter_by(username=username).first()
            except Exception:
                logging.exception("DB error while looking up user %s", username)
                skipped += 1
                continue

            if existing:
                # Update email if missing and admin has one
                if (not getattr(existing, "email", None)) and email:
                    msg = f"Would set email for user {username} -> {email}" if dry_run else f"Setting email for user {username} -> {email}"
                    logging.info(msg)
                    if not dry_run:
                        try:
                            existing.email = email
                            db.session.add(existing)
                            db.session.commit()
                            updated += 1
                        except Exception:
                            db.session.rollback()
                            logging.exception("Failed to update user %s", username)
                else:
                    logging.info("User %s already exists, skipping", username)
                    skipped += 1
                continue

            # Create new User row for admin
            logging.info("Creating User for admin: %s (email=%s) %s", username, email, "(dry-run)" if dry_run else "")
            if dry_run:
                created += 1
                logging.info("(dry-run) would create user %s", username)
                # Show candidate password if any
                if fixed_password:
                    logging.info("(dry-run) would set password from --password")
                else:
                    logging.info("(dry-run) would generate random password")
                continue

            try:
                # Determine password to use: fixed or generated
                if fixed_password:
                    pw = fixed_password
                else:
                    pw = secrets.token_urlsafe(18)

                new_user = User(username=username, email=email)
                try:
                    # Prefer set_password if model exposes it
                    new_user.set_password(pw)
                except Exception:
                    try:
                        # Fallback: set attribute `password_hash` if present
                        if hasattr(new_user, "password_hash"):
                            new_user.password_hash = pw
                    except Exception:
                        pass

                # Try to copy role if AdminUser exposes it
                try:
                    if hasattr(au, "role") and hasattr(new_user, "role"):
                        new_user.role = getattr(au, "role")
                except Exception:
                    pass

                db.session.add(new_user)
                db.session.commit()
                created += 1
                logging.info("Created user %s (id=%s)", username, getattr(new_user, "id", "?"))

                # If commit and log file requested, append username:password line
                if log_file_path:
                    try:
                        with open(log_file_path, "a", encoding="utf-8") as fh:
                            fh.write(f"{username}:{pw}\n")
                    except Exception:
                        logging.exception("Failed to write password log to %s", log_file_path)
            except Exception:
                db.session.rollback()
                logging.exception("Failed to create user for admin %s", username)

    logging.info("Done. created=%d updated=%d skipped=%d", created, updated, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
