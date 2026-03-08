#!/usr/bin/env python3
"""
Reset or create an admin user password in a HelpChain SQLite database.

Works directly with sqlite3 (no Flask app startup), which is useful when the
runtime DB layer is noisy or when you want a quick offline recovery.

Examples:
  python scripts/reset_admin_password.py --db instance/hc_run.db
  python scripts/reset_admin_password.py --db backend/instance/app_clean_copy.db --copy-to hc_magic_adminfix.db
  python scripts/reset_admin_password.py --db hc_magic_adminfix.db --username admin --password "NewStrongPass123!"
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import sqlite3
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.local_db_guard import (
    APP_IMPORT_PATH,
    canonical_confirmation_error,
    canonical_mismatch_error,
    db_path_from_sqlite_uri,
    is_canonical_db_uri,
    print_app_db_preflight,
)


def _default_db_path(project_root: Path) -> Path:
    return project_root / "backend" / "instance" / "app_clean.db"


def _gen_password() -> str:
    return "HCAdmin-" + secrets.token_urlsafe(9)


def _ensure_admin_row(
    con: sqlite3.Connection,
    *,
    username: str,
    email: str,
    password_hash: str,
) -> str:
    cur = con.cursor()
    row = cur.execute(
        "SELECT id FROM admin_users WHERE username = ? LIMIT 1", (username,)
    ).fetchone()
    if row:
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, is_active = 1 WHERE username = ?",
            (password_hash, username),
        )
        return "UPDATED"
    cur.execute(
        """
        INSERT INTO admin_users (username, email, password_hash, role, is_active, mfa_enabled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username, email, password_hash, "admin", 1, 0),
    )
    return "CREATED"


def main() -> int:
    project_root = PROJECT_ROOT
    parser = argparse.ArgumentParser(description="Reset HelpChain admin password")
    parser.add_argument(
        "--db",
        type=Path,
        default=_default_db_path(project_root),
        help="Path to SQLite DB file (default: instance/hc_run.db)",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        default=None,
        help="Optional output DB copy to patch instead of modifying the source DB",
    )
    parser.add_argument("--username", default="admin", help="Admin username")
    parser.add_argument(
        "--email", default="admin@helpchain.live", help="Email to use if user is created"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="New password (if omitted, a strong password is generated)",
    )
    parser.add_argument(
        "--print-login-url",
        action="store_true",
        help="Print admin login URL after reset",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for printed login URL")
    parser.add_argument("--port", default="5000", help="Port for printed login URL")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow DB write",
    )
    args = parser.parse_args()

    from backend.appy import app

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error(), file=sys.stderr)
            return 2
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri), file=sys.stderr)
            return 2

    src_db = args.db if args.db.is_absolute() else (project_root / args.db)
    target_db = (
        (args.copy_to if args.copy_to.is_absolute() else (project_root / args.copy_to))
        if args.copy_to
        else src_db
    )
    canonical_db_path = db_path_from_sqlite_uri(runtime_uri)
    if canonical_db_path is None:
        print(f"ERROR: runtime DB is not sqlite: {runtime_uri}", file=sys.stderr)
        return 2
    canonical_db_path = canonical_db_path.resolve()
    if src_db.resolve() != canonical_db_path:
        print("ERROR: --db must point to canonical DB file only.", file=sys.stderr)
        print(f"Expected DB path: {canonical_db_path}", file=sys.stderr)
        print(f"Provided DB path: {src_db.resolve()}", file=sys.stderr)
        return 2
    if args.copy_to:
        print("ERROR: --copy-to is disabled by local DB safety rules.", file=sys.stderr)
        return 2

    if not src_db.exists():
        print(f"ERROR: DB file not found: {src_db}", file=sys.stderr)
        return 2

    if args.copy_to:
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, target_db)

    new_password = args.password or _gen_password()
    pw_hash = generate_password_hash(new_password)

    try:
        con = sqlite3.connect(str(target_db), timeout=5)
        cur = con.cursor()
        # More resilient for local recovery on Windows / flaky SQLite journals.
        cur.execute("PRAGMA journal_mode=OFF")
        cur.execute("PRAGMA synchronous=OFF")
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "admin_users" not in tables:
            print(
                f"ERROR: Table 'admin_users' not found in DB: {target_db}",
                file=sys.stderr,
            )
            return 3
        status = _ensure_admin_row(
            con,
            username=args.username.strip(),
            email=args.email.strip(),
            password_hash=pw_hash,
        )
        con.commit()
        integrity = cur.execute("PRAGMA integrity_check").fetchone()
        con.close()
    except sqlite3.Error as e:
        print(f"ERROR: sqlite failure: {e}", file=sys.stderr)
        return 4

    print(f"DB={target_db}")
    print(f"STATUS={status}")
    print(f"USERNAME={args.username}")
    print(f"PASSWORD={new_password}")
    print(f"INTEGRITY={integrity}")
    if args.print_login_url:
        print(f"LOGIN_URL=http://{args.host}:{args.port}/admin/ops/login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
