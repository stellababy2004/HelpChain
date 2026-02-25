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


def _default_db_path(project_root: Path) -> Path:
    return project_root / "instance" / "hc_run.db"


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
    project_root = Path(__file__).resolve().parents[1]
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
    args = parser.parse_args()

    src_db = args.db if args.db.is_absolute() else (project_root / args.db)
    target_db = (
        (args.copy_to if args.copy_to.is_absolute() else (project_root / args.copy_to))
        if args.copy_to
        else src_db
    )

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
