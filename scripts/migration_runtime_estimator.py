from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PATTERNS = {
    "create_index": r"create_index\(",
    "alter_column": r"alter_column\(",
    "add_column": r"add_column\(",
    "drop_column": r"drop_column\(",
}


def detect_operations(text: str):

    ops = []

    for line in text.splitlines():

        for name, pattern in PATTERNS.items():

            if re.search(pattern, line):

                table = None

                match = re.search(r"'([a-zA-Z0-9_]+)'", line)

                if match:
                    table = match.group(1)

                ops.append((name, table))

    return ops


def estimate_cost(operation: str, rows: int):

    if rows == 0:
        rows = 1

    if operation == "create_index":
        time = rows * 0.00002
        lock = "READ LOCK"

    elif operation == "alter_column":
        time = rows * 0.00005
        lock = "TABLE REWRITE"

    elif operation == "add_column":
        time = rows * 0.00001
        lock = "LOW"

    elif operation == "drop_column":
        time = rows * 0.00003
        lock = "EXCLUSIVE"

    else:
        time = rows * 0.00001
        lock = "UNKNOWN"

    return round(time, 2), lock


def get_table_rows(engine, table):

    try:
        result = engine.execute(text(f"SELECT COUNT(*) FROM {table}"))
        return result.scalar() or 0
    except Exception:
        return 0


def main():

    print("\nMigration Runtime Estimator\n")

    from backend.helpchain_backend.src.app import create_app
    from backend.extensions import db

    app = create_app()

    total_time = 0

    with app.app_context():

        engine = db.engine

        for f in sorted(MIGRATIONS.glob("*.py")):

            text_data = f.read_text(encoding="utf-8")

            operations = detect_operations(text_data)

            if not operations:
                continue

            print("\n", f.name)

            for op, table in operations:

                rows = get_table_rows(engine, table) if table else 0

                time_est, lock = estimate_cost(op, rows)

                total_time += time_est

                print(
                    f"{op:15} table={table or '-':20} rows={rows:8} "
                    f"est_time={time_est:6}s lock={lock}"
                )

    print("\nEstimated total migration time:", round(total_time, 2), "seconds")

    if total_time > 60:
        print("\nWARNING: Migration may cause downtime")

    elif total_time > 10:
        print("\nModerate runtime expected")

    else:
        print("\nMigration runtime likely safe")


if __name__ == "__main__":
    main()
