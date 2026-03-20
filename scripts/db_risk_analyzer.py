from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LARGE_TABLE_HINTS = {"users", "requests", "cases", "assignments", "admin_users", "professional_leads", "volunteers"}
FILTER_COLUMNS = {"status", "state", "created_at", "updated_at", "email", "username", "structure_id"}


def _print(title: str) -> None:
    print(f"\n{title}")


def _risk(level: str, table: str, issue: str, suggestion: str) -> None:
    print(f"Table: {table}")
    print(f"Issue: {issue}")
    print(f"Risk: {level}")
    print(f"Suggestion: {suggestion}")
    print()


def _scan_code_for_antipatterns() -> list[str]:
    issues = []
    route_files = list((ROOT / "backend" / "helpchain_backend" / "src" / "routes").glob("*.py"))
    for path in route_files:
        text = path.read_text(encoding="utf-8")
        if ".query.all()" in text or ".query.all()" in text:
            issues.append(f"Potential query.all() on {path.name}")
        if ".join(" in text and ".options(" not in text:
            if "joinedload" not in text and "selectinload" not in text:
                issues.append(f"Potential N+1 risk in {path.name}")
    return issues


def main() -> int:
    try:
        from backend.helpchain_backend.src.app import create_app
        from backend.extensions import db
    except Exception as exc:
        print("FAILED TO IMPORT APP/DB:", exc)
        return 2

    app = create_app()
    risks_found = False

    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        _print("DATABASE RISK ANALYSIS")

        for table in tables:
            cols = inspector.get_columns(table)
            indexes = inspector.get_indexes(table)
            index_cols = {c for idx in indexes for c in idx.get("column_names", [])}

            # Missing indexes on FK columns
            fks = inspector.get_foreign_keys(table)
            for fk in fks:
                for col in fk.get("constrained_columns", []):
                    if col not in index_cols:
                        risks_found = True
                        _risk(
                            "HIGH",
                            table,
                            f"FK without index: {col}",
                            f"create index ix_{table}_{col}",
                        )

            # Frequently filtered columns
            for c in cols:
                name = c["name"]
                if name in FILTER_COLUMNS and name not in index_cols:
                    risks_found = True
                    _risk(
                        "MEDIUM",
                        table,
                        f"missing index on {name}",
                        f"create index ix_{table}_{name}",
                    )

            # Large table hint without any indexes
            if table in LARGE_TABLE_HINTS and not indexes:
                risks_found = True
                _risk(
                    "HIGH",
                    table,
                    "large table without indexes",
                    "add indexes on FK/status/created_at",
                )

    _print("ORM ANTI-PATTERNS")
    anti = _scan_code_for_antipatterns()
    if anti:
        risks_found = True
        for issue in anti:
            print(issue)

    return 1 if risks_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
