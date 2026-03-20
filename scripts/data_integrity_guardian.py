from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print(title: str) -> None:
    print(f"\n{title}")


def main() -> int:
    try:
        from backend.helpchain_backend.src.app import create_app
        from backend.extensions import db
    except Exception as exc:
        print("FAILED TO IMPORT APP/DB:", exc)
        return 2

    app = create_app()
    issues_found = False

    with app.app_context():
        insp = inspect(db.engine)
        tables = insp.get_table_names()

        _print("DATA INTEGRITY REPORT")

        # Orphan records / broken FKs
        for table in tables:
            fks = insp.get_foreign_keys(table)
            for fk in fks:
                ref_table = fk.get("referred_table")
                local_cols = fk.get("constrained_columns") or []
                remote_cols = fk.get("referred_columns") or []
                if not ref_table or not local_cols or not remote_cols:
                    continue
                for lcol, rcol in zip(local_cols, remote_cols):
                    sql = f"""
                        SELECT t.{lcol} AS orphan_id
                        FROM {table} t
                        LEFT JOIN {ref_table} r ON t.{lcol} = r.{rcol}
                        WHERE t.{lcol} IS NOT NULL AND r.{rcol} IS NULL
                        LIMIT 10
                    """
                    rows = db.session.execute(text(sql)).fetchall()
                    if rows:
                        issues_found = True
                        print(f"Table: {table}")
                        print("Issue: orphan record")
                        for row in rows:
                            print(f"{lcol}: {row[0]}")
                        print("Risk: HIGH")
                        print()

        # Duplicate values on unique columns
        for table in tables:
            uniques = insp.get_unique_constraints(table)
            for uq in uniques:
                cols = uq.get("column_names") or []
                if not cols:
                    continue
                col_list = ", ".join(cols)
                sql = f"""
                    SELECT {col_list}, COUNT(*) c
                    FROM {table}
                    GROUP BY {col_list}
                    HAVING COUNT(*) > 1
                    LIMIT 10
                """
                rows = db.session.execute(text(sql)).fetchall()
                if rows:
                    issues_found = True
                    print(f"Table: {table}")
                    print("Issue: duplicate on unique constraint")
                    print(f"Columns: {col_list}")
                    print("Risk: HIGH")
                    for row in rows:
                        print(row)
                    print()

        # Invalid status/enum values (heuristic: columns named status/state/type)
        for table in tables:
            cols = [c["name"] for c in insp.get_columns(table)]
            for col in cols:
                if col in {"status", "state", "type"}:
                    sql = f"SELECT DISTINCT {col} FROM {table} LIMIT 20"
                    rows = db.session.execute(text(sql)).fetchall()
                    if rows and any(r[0] is None for r in rows):
                        issues_found = True
                        print(f"Table: {table}")
                        print(f"Issue: invalid/NULL {col}")
                        print("Risk: MEDIUM")
                        print()

    return 1 if issues_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
