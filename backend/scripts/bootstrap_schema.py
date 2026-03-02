"""Best-effort runtime schema bootstrap for environments with migration drift.

Creates missing tables from SQLAlchemy metadata. Does not alter existing tables.
"""

from __future__ import annotations

from sqlalchemy import inspect

from backend.appy import app
from backend.extensions import db

# Ensure model metadata is loaded before create_all().
import backend.models  # noqa: F401
import backend.helpchain_backend.src.models  # noqa: F401


def main() -> int:
    with app.app_context():
        engine = db.engine
        insp = inspect(engine)
        before = set(insp.get_table_names())
        db.create_all()
        after = set(inspect(engine).get_table_names())
        created = sorted(after - before)
        if created:
            print(f"SCHEMA_BOOTSTRAP: created tables: {', '.join(created)}")
        else:
            print("SCHEMA_BOOTSTRAP: no missing tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
