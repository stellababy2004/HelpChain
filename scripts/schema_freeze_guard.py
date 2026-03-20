from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd, cwd=str(ROOT))


def _latest_revision() -> str | None:
    alembic_ini = ROOT / "migrations" / "alembic.ini"
    if not alembic_ini.exists():
        return None
    config = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def main() -> int:
    try:
        from backend.helpchain_backend.src.app import create_app
        from backend.extensions import db
    except Exception as exc:
        print("FAILED TO IMPORT APP/DB:", exc)
        return 2

    app = create_app()
    with app.app_context():
        try:
            row = db.session.execute(db.text("SELECT version_num FROM alembic_version")).fetchone()
            db_rev = row[0] if row else None
        except Exception as exc:
            print("FAILED TO READ ALEMBIC VERSION:", exc)
            return 2

    latest = _latest_revision()
    if latest and db_rev != latest:
        print("DATABASE NOT UPGRADED TO LATEST MIGRATION")
        return 1

    # reuse drift detector
    drift_cmd = [sys.executable, str(ROOT / "backend" / "tools" / "migration_drift_detector.py")]
    if _run(drift_cmd) != 0:
        print("SCHEMA DRIFT DETECTED — DEPLOY BLOCKED")
        return 1

    print("SCHEMA FREEZE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
