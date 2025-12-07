#!/usr/bin/env python3
"""Safe launcher for running the backend app.

Usage:
  # Quick import check (no server started)
  python run_backend.py

  # Start the server (runs `python -m backend.appy`)
  python run_backend.py --start

This is intentionally conservative: importing `backend.appy` as a module verifies
all package-relative imports (e.g. `from .models`) succeed when run from the
project root. Starting the server is opt-in via --start to avoid accidental
long-running processes during verification.
"""

import argparse
import importlib
import os
import subprocess
import sys
from typing import Optional


def import_check() -> int:
    """Attempt to import the application module. Return 0 on success, 2 on error.

    Importing `backend.appy` validates package-relative imports and basic
    initialization but does not start the server (module __main__ block won't
    run on import)."""
    try:
        importlib.import_module("backend.appy")
        print("IMPORT_OK")
        return 0
    except Exception:
        import traceback

        traceback.print_exc()
        return 2


def start_server() -> int:
    """Start the backend by running the module as __main__ (explicit action).

    This uses `python -m backend.appy` so the package imports resolve the same
    way they do for import_check, but executes the server main code. This
    operation is intentionally opt-in to avoid accidental long-running
    processes during automated checks.
    """
    cmd = [sys.executable, "-m", "backend.appy"]
    print("Starting backend.appy via:", " ".join(cmd))
    return subprocess.call(cmd)


def _run_run_migrations(database_url: str, run_migrations_path: str) -> int:
    """Invoke the repository's run_migrations.py script with DATABASE_URL set.

    Returns subprocess return code (0 success), 3 if script missing.
    """
    env = os.environ.copy()
    if database_url:
        env["DATABASE_URL"] = database_url
    cmd = [sys.executable, run_migrations_path]
    print("Running migrations via:", " ".join(cmd))
    try:
        return subprocess.call(cmd, env=env)
    except FileNotFoundError:
        print("run_migrations.py not found at:", run_migrations_path)
        return 3


def init_db(seed_admin: bool = False) -> int:
    """Initialize DB: try run_migrations.py, else fallback to db.create_all().

    If seed_admin is True, call initialize_default_admin() in app context
    if that function is available.
    """
    try:
        mod = importlib.import_module("backend.appy")
    except Exception:
        print("Failed to import backend.appy for DB initialization", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 2

    app = getattr(mod, "app", None)
    db = getattr(mod, "db", None)
    if db is None:
        try:
            ext = importlib.import_module("backend.extensions")
            db = getattr(ext, "db", None)
        except Exception:
            db = None

    if app is None or db is None:
        print(
            "App or DB object not found in backend.appy; cannot initialize DB",
            file=sys.stderr,
        )
        return 2

    run_migrations_path = os.path.join(os.path.dirname(__file__), "backend", "run_migrations.py")
    database_url = app.config.get("SQLALCHEMY_DATABASE_URI")

    rc_mig = None
    if os.path.isfile(run_migrations_path):
        rc_mig = _run_run_migrations(database_url or "", run_migrations_path)
        if rc_mig == 0:
            print("Migrations applied successfully")
        else:
            print(f"Migrations script returned {rc_mig}; will fall back to db.create_all()")
    else:
        print("No run_migrations.py found; falling back to db.create_all()")

    # Fallback to create_all inside app context
    try:
        with app.app_context():
            try:
                db.create_all()
                print("db.create_all() completed")
            except Exception:
                import traceback

                print("db.create_all() failed, see traceback below:")
                traceback.print_exc()
                return 3

            if seed_admin:
                init_fn = getattr(mod, "initialize_default_admin", None)
                if callable(init_fn):
                    try:
                        init_fn()
                        print("Default admin seeded (initialize_default_admin executed)")
                    except Exception:
                        import traceback

                        print("Seeding admin failed:")
                        traceback.print_exc()
                        return 4
                else:
                    print("initialize_default_admin not available in backend.appy; skipping seed")

    except Exception:
        import traceback

        print("Failed to initialize DB within app context:")
        traceback.print_exc()
        return 5

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Conservative launcher for HelpChain backend. By default this script only verifies that `backend.appy` can be imported. Use --start to actually run the server.")
    )
    parser.add_argument("--start", action="store_true", help="Start the server")
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Run migrations (if available) or fall back to db.create_all()",
    )
    parser.add_argument(
        "--seed-admin",
        action="store_true",
        help="After --init-db, seed a default admin user (if supported)",
    )
    args = parser.parse_args(argv)

    if args.start:
        return start_server()
    if args.init_db:
        return init_db(seed_admin=args.seed_admin)
    # Default: import-only check
    return import_check()


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
