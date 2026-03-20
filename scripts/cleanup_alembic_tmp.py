from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from backend.helpchain_backend.src.config import Config


def _sqlite_path(uri: str) -> Path | None:
    if not uri.startswith("sqlite:"):
        return None

    parsed = urlparse(uri)
    if parsed.scheme != "sqlite":
        return None

    # sqlite:///C:/path or sqlite:////abs/path
    path = parsed.path
    if path.startswith("/") and len(path) > 3 and path[2] == ":":
        # Windows drive letter
        path = path[1:]
    return Path(path)


def main() -> None:
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    db_path = _sqlite_path(db_uri)

    if not db_path:
        print("Non-SQLite DB detected. No cleanup needed.")
        return

    if not db_path.exists():
        print("Database not found:", db_path)
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '_alembic_tmp_%'
        """
    )

    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        print("No Alembic temp tables found.")
        conn.close()
        return

    for table in tables:
        print("Removing:", table)
        cur.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()
    conn.close()

    print("Alembic temp tables cleaned.")


if __name__ == "__main__":
    main()
