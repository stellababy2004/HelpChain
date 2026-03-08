from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Show DB migration status visibility")
    parser.add_argument(
        "--fail-on-outdated",
        action="store_true",
        help="Return non-zero when DB revision differs from Alembic head",
    )
    args = parser.parse_args()

    from backend.appy import app
    from backend.models import db

    with app.app_context():
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print("APP: backend.appy:app")
        print(f"DB: {uri}")

        tables = set(inspect(db.engine).get_table_names())
        db_revisions: list[str] = []
        if "alembic_version" in tables:
            rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            db_revisions = sorted({str(r[0]).strip() for r in rows if r and r[0]})

        head_revisions: list[str] = []
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            cfg = Config()
            cfg.set_main_option("script_location", "migrations")
            script = ScriptDirectory.from_config(cfg)
            head_revisions = sorted(script.get_heads() or [])
        except Exception as exc:
            print(f"ALEMBIC_HEAD_WARNING: {exc}")

        db_rev_text = ",".join(db_revisions) if db_revisions else "none"
        head_rev_text = ",".join(head_revisions) if head_revisions else "none"

        if db_revisions and head_revisions:
            status = "OK" if set(db_revisions) == set(head_revisions) else "OUT OF DATE"
        else:
            status = "UNKNOWN"

        print(f"DB_MIGRATION_REVISION={db_rev_text}")
        print(f"ALEMBIC_HEAD_REVISION={head_rev_text}")
        print(f"MIGRATION_STATUS={status}")

        if args.fail_on_outdated and status != "OK":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
