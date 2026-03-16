from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


def _db_path() -> Path:
    env_url = (os.getenv("DATABASE_URL") or "").strip()
    if env_url.startswith("sqlite:///"):
        return Path(env_url.replace("sqlite:///", ""))
    # Default local path used by the app in this repo
    return Path(__file__).resolve().parents[2] / "backend" / "instance" / "app_clean.db"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT,
            is_active INTEGER,
            structure_id INTEGER,
            totp_secret TEXT,
            mfa_enabled INTEGER,
            mfa_enrolled_at TEXT,
            backup_codes_hashes TEXT,
            backup_codes_generated_at TEXT
        )
        """
    )
    conn.commit()


def _upsert_admin(
    conn: sqlite3.Connection,
    *,
    username: str,
    email: str,
    role: str,
    structure_id: int | None,
    password: str,
) -> None:
    pwd_hash = generate_password_hash(password)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM admin_users WHERE username = ? OR email = ?",
        (username, email),
    )
    row = cur.fetchone()
    if row:
        admin_id = row[0]
        cur.execute(
            """
            UPDATE admin_users
            SET username = ?, email = ?, password_hash = ?, role = ?, is_active = ?, structure_id = ?
            WHERE id = ?
            """,
            (username, email, pwd_hash, role, 1, structure_id, admin_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO admin_users (username, email, password_hash, role, is_active, structure_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, pwd_hash, role, 1, structure_id),
        )
    conn.commit()


def main() -> None:
    db_path = _db_path()
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return
    conn = sqlite3.connect(str(db_path))
    _ensure_table(conn)

    _upsert_admin(
        conn,
        username="superadmin",
        email="superadmin@local.test",
        role="superadmin",
        structure_id=None,
        password="DevAdmin123!",
    )
    _upsert_admin(
        conn,
        username="structureadmin",
        email="structureadmin@local.test",
        role="admin",
        structure_id=2,
        password="DevStructure123!",
    )
    _upsert_admin(
        conn,
        username="operator",
        email="operator@local.test",
        role="ops",
        structure_id=2,
        password="DevOperator123!",
    )

    print("Local admin accounts ready:")
    print(" - superadmin / DevAdmin123! (role=superadmin, structure_id=NULL)")
    print(" - structureadmin / DevStructure123! (role=admin, structure_id=2)")
    print(" - operator / DevOperator123! (role=ops, structure_id=2)")
    print(f"DB: {db_path}")
    conn.close()


if __name__ == "__main__":
    main()
