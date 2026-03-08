from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.local_db_guard import (
    APP_IMPORT_PATH,
    CANONICAL_DB_URI,
    detect_legacy_sqlite_hint,
    is_canonical_db_uri,
)


def main() -> int:
    try:
        from backend.appy import app
        from backend.models import db
    except Exception as exc:
        print(f"ERROR: failed to import {APP_IMPORT_PATH}: {exc}")
        return 1

    print(f"APP: {APP_IMPORT_PATH}")

    try:
        with app.app_context():
            uri = app.config.get("SQLALCHEMY_DATABASE_URI")
            print(f"DB: {uri}")
            print(f"APP_IMPORT_PATH={APP_IMPORT_PATH}")
            print(f"SQLALCHEMY_DATABASE_URI={uri}")
            print(f"CANONICAL_SQLALCHEMY_DATABASE_URI={CANONICAL_DB_URI}")
            print(f"DB_TARGET_IS_CANONICAL={str(is_canonical_db_uri(uri)).lower()}")
            legacy_hint = detect_legacy_sqlite_hint(uri)
            if legacy_hint:
                print(f"WARNING_LEGACY_SQLITE_TARGET={legacy_hint}")

            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())

            for table_name in ("requests", "admin_users"):
                exists = table_name in tables
                print(f"TABLE_{table_name.upper()}_EXISTS={str(exists).lower()}")
                if exists:
                    count = db.session.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")
                    ).scalar_one()
                    print(f"TABLE_{table_name.upper()}_COUNT={count}")
    except Exception as exc:
        print(f"ERROR: runtime inspection failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
