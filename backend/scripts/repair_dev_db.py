from __future__ import annotations

import pathlib
import sqlite3
import sys
from datetime import datetime, UTC

from werkzeug.security import generate_password_hash

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app


DB_PATH = ROOT / "backend" / "instance" / "app.db"


USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255),
    password_hash VARCHAR(255),
    created_at DATETIME,
    structure_id INTEGER
)
"""

ADMIN_USERS_DDL = """
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(50),
    structure_id INTEGER,
    created_at DATETIME
)
"""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_tables(conn: sqlite3.Connection) -> list[str]:
    created = []
    if not _table_exists(conn, "users"):
        conn.execute(USERS_DDL)
        created.append("users")
    if not _table_exists(conn, "admin_users"):
        conn.execute(ADMIN_USERS_DDL)
        created.append("admin_users")
    return created


def _admin_exists(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "admin_users"):
        return False
    row = conn.execute("SELECT id FROM admin_users LIMIT 1").fetchone()
    return row is not None


def _create_default_admin(conn: sqlite3.Connection) -> bool:
    if _admin_exists(conn):
        return False
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO admin_users (username, password_hash, role, structure_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "admin",
            generate_password_hash("943415StoyanovaNova!"),
            "superadmin",
            None,
            now,
        ),
    )
    return True


def _check_routes() -> dict[str, bool]:
    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    return {
        "/admin/login": "/admin/login" in rules,
        "/admin": "/admin" in rules or "/admin/" in rules,
        "/admin/command": "/admin/command" in rules,
    }


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database file missing: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        created = _ensure_tables(conn)
        admin_created = _create_default_admin(conn)
        conn.commit()
    finally:
        conn.close()

    if created:
        print(f"Created tables: {', '.join(created)}")
    else:
        print("Database tables OK")

    if admin_created:
        print("Admin user created")
    else:
        print("Admin user exists")

    route_status = _check_routes()
    for route, ok in route_status.items():
        print(f"Route {route}: {'OK' if ok else 'MISSING'}")

    print("System ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
