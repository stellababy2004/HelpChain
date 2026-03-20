from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def collect_temp_tables(engine):
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    tmp_tables = [t for t in tables if t.startswith("_alembic_tmp_")]

    return tmp_tables


def collect_orphan_indexes(engine):
    inspector = inspect(engine)

    orphan = []

    tables = inspector.get_table_names()

    for table in tables:
        indexes = inspector.get_indexes(table)

        for idx in indexes:
            name = idx.get("name")
            cols = idx.get("column_names")

            if not name:
                continue

            # ignore SQLite auto indexes
            if name.startswith("sqlite_autoindex"):
                continue

            if name.startswith("_alembic_tmp_"):
                orphan.append((table, name))

    return orphan


def drop_temp_tables(engine, tables):
    if not tables:
        return

    print("\nDropping temporary Alembic tables")

    with engine.begin() as conn:
        for t in tables:
            print("  DROP TABLE", t)
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))


def drop_orphan_indexes(engine, indexes):
    if not indexes:
        return

    print("\nDropping orphan indexes")

    with engine.begin() as conn:
        for table, idx in indexes:
            print("  DROP INDEX", idx)
            conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))


def main() -> int:
    from backend.helpchain_backend.src.app import create_app
    from backend.extensions import db

    app = create_app()

    with app.app_context():
        engine = db.engine

        print("\nMigration Garbage Collector\n")

        tmp_tables = collect_temp_tables(engine)
        orphan_indexes = collect_orphan_indexes(engine)

        if not tmp_tables and not orphan_indexes:
            print("Database clean — nothing to collect.")
            return 0

        if tmp_tables:
            print("\nTemporary Alembic tables:")
            for t in tmp_tables:
                print(" ", t)

        if orphan_indexes:
            print("\nOrphan indexes:")
            for table, idx in orphan_indexes:
                print(f" {table}.{idx}")

        drop_temp_tables(engine, tmp_tables)
        drop_orphan_indexes(engine, orphan_indexes)

        print("\nGarbage collection complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
