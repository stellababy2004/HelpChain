from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_header(title: str) -> None:
    print(f"\n{title}")


def main() -> int:
    try:
        from backend.helpchain_backend.src.app import create_app
        from backend.extensions import db
        from backend.helpchain_backend.src.models import Case
    except Exception as exc:
        print("FAILED TO IMPORT APP/DB:", exc)
        return 2

    app = create_app()
    status_ok = True

    with app.app_context():
        engine_url = str(db.engine.url)

        _print_header("ACTIVE DATABASE")
        print(engine_url)

        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        _print_header("ALEMBIC VERSION")
        if "alembic_version" in tables:
            try:
                row = db.session.execute(
                    db.text("SELECT version_num FROM alembic_version")
                ).fetchone()
                print(row[0] if row else "<empty>")
            except Exception as exc:
                status_ok = False
                print("ERROR READING ALEMBIC VERSION:", exc)
        else:
            status_ok = False
            print("MISSING TABLE: alembic_version")

        _print_header("CRITICAL TABLES")
        for name in ("users", "requests", "cases", "structures", "volunteers"):
            if name not in tables:
                status_ok = False
                print(f"MISSING TABLE: {name}")

        _print_header("CASES SCHEMA")
        if "cases" in tables:
            case_cols = {c["name"] for c in inspector.get_columns("cases")}
            required = {"id", "request_id", "latitude", "longitude", "status", "priority"}
            for col in sorted(required):
                if col not in case_cols:
                    status_ok = False
                    print(f"SCHEMA DRIFT DETECTED: cases.{col} missing")
        else:
            status_ok = False
            print("SCHEMA DRIFT DETECTED: cases table missing")

        _print_header("ORM VS DB")
        if "cases" in tables:
            case_cols = {c["name"] for c in inspector.get_columns("cases")}
            model_cols = set(Case.__table__.columns.keys())
            for col in sorted(model_cols - case_cols):
                status_ok = False
                print(f"MODEL COLUMN NOT IN DATABASE: cases.{col}")
            for col in sorted(case_cols - model_cols):
                print(f"DATABASE COLUMN NOT IN MODEL: cases.{col}")

        _print_header("MIGRATION STATUS")
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            alembic_cfg = Config(str(ROOT / "migrations" / "alembic.ini"))
            script = ScriptDirectory.from_config(alembic_cfg)
            heads = set(script.get_heads())
            db_rev = None
            if "alembic_version" in tables:
                row = db.session.execute(
                    db.text("SELECT version_num FROM alembic_version")
                ).fetchone()
                db_rev = row[0] if row else None
            if db_rev not in heads:
                status_ok = False
                print("UNAPPLIED MIGRATIONS DETECTED")
        except Exception as exc:
            status_ok = False
            print("MIGRATION STATUS CHECK FAILED:", exc)

    _print_header("SUMMARY")
    if status_ok:
        print("DATABASE STATUS: OK")
    else:
        print("DATABASE STATUS: MIGRATION REQUIRED")
        print("RECOMMENDED COMMANDS:")
        print("flask db upgrade")

    return 0 if status_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
