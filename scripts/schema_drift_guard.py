import os
import sqlite3
import sys

# Ensure project root is importable when running as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import models as m
from backend.extensions import db
from backend.helpchain_backend.src.app import create_app


def sqlite_table_columns(db_path: str, table_name: str) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table_name});")
        rows = cur.fetchall()
        return {r[1] for r in rows}  # column name
    finally:
        con.close()


def orm_model_columns(model) -> set[str]:
    # Only works for Flask-SQLAlchemy models (db.Model)
    return {c.name for c in model.__table__.columns}


def drift_for_model(db_path: str, model) -> tuple[str, set[str], set[str]]:
    table = model.__table__.name
    orm_cols = orm_model_columns(model)
    sql_cols = sqlite_table_columns(db_path, table)
    extra_in_orm = orm_cols - sql_cols
    missing_in_orm = sql_cols - orm_cols
    return table, extra_in_orm, missing_in_orm


def main() -> int:
    app = create_app()

    # IMPORTANT: app.db path is instance/app.db in your setup
    db_path = os.path.join(PROJECT_ROOT, "instance", "app.db")
    if not os.path.exists(db_path):
        print(f"[DRIFT] DB file not found: {db_path}")
        return 2

    targets = [
        m.User,
        m.Volunteer,
        m.Request,
    ]

    with app.app_context():
        problems: list[str] = []
        print("== SCHEMA DRIFT GUARD ==")
        print("DB:", db_path)

        for model in targets:
            table, extra_in_orm, missing_in_orm = drift_for_model(db_path, model)

            if extra_in_orm or missing_in_orm:
                problems.append(table)
                print(f"\n[DRIFT] table={table}")
                if extra_in_orm:
                    print("  - In ORM but NOT in DB:", sorted(extra_in_orm))
                if missing_in_orm:
                    print("  - In DB but NOT in ORM:", sorted(missing_in_orm))
            else:
                print(f"[OK] {table} (ORM == DB)")

        if problems:
            print("\n[FAIL] Drift detected in:", ", ".join(problems))
            return 1

        print("\n[PASS] No drift detected for User/Volunteer/Request.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
