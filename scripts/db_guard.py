from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _print(msg: str) -> None:
    print(msg)


def _read_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return {}
    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"')
    return data


def _resolve_db_path() -> Path | None:
    env = dict(os.environ)
    if not env.get("SQLALCHEMY_DATABASE_URI") or not env.get("DATABASE_URL"):
        env.update(_read_env_file())
    uri = env.get("SQLALCHEMY_DATABASE_URI") or env.get("DATABASE_URL") or ""
    if not uri:
        uri = f"sqlite:///{(ROOT / 'backend' / 'instance' / 'app.db').as_posix()}"
    if not uri.startswith("sqlite:"):
        _print(f"UNSUPPORTED DATABASE URL: {uri}")
        return None
    path = uri.replace("sqlite:///", "", 1).replace("sqlite://", "", 1)
    path = path.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", path):
        return Path(path)
    return (ROOT / path).resolve()


def _backup(db_path: Path) -> Path:
    backups_dir = db_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"{db_path.stem}_{ts}.db"
    shutil.copy2(db_path, backup_path)
    _print("DATABASE BACKUP CREATED")
    _print(str(backup_path))
    return backup_path


def _latest_backup(db_path: Path) -> Path | None:
    backups_dir = db_path.parent / "backups"
    if not backups_dir.exists():
        return None
    backups = sorted(backups_dir.glob(f"{db_path.stem}_*.db"), reverse=True)
    return backups[0] if backups else None


def _restore(db_path: Path) -> bool:
    backup = _latest_backup(db_path)
    if not backup:
        _print("NO BACKUP FOUND")
        return False
    shutil.copy2(backup, db_path)
    _print("ROLLBACK APPLIED")
    _print(str(backup))
    return True


def _run_flask_cmd(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "flask", "--app", "backend.appy:app"] + args
    return subprocess.call(cmd, cwd=str(ROOT))


def _validate() -> bool:
    rc = _run_flask_cmd(["db", "upgrade", "--sql"])
    if rc != 0:
        _print("MIGRATION VALIDATION FAILED")
        return False
    _print("MIGRATION VALIDATED")
    return True


def _upgrade() -> bool:
    rc = _run_flask_cmd(["db", "upgrade"])
    if rc != 0:
        _print("MIGRATION FAILED")
        return False
    _print("MIGRATION APPLIED")
    return True


def _schema_check(db_path: Path) -> bool:
    required = {"latitude", "longitude", "status", "priority"}
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cases'")
    if not cur.fetchone():
        con.close()
        _print("SCHEMA VALIDATION FAILED")
        return False
    cur.execute("PRAGMA table_info(cases)")
    cols = {r[1] for r in cur.fetchall()}
    con.close()
    missing = sorted(required - cols)
    if missing:
        _print("SCHEMA VALIDATION FAILED")
        for col in missing:
            _print(f"MISSING COLUMN: cases.{col}")
        return False
    _print("SCHEMA VALID")
    return True


def cmd_backup(db_path: Path) -> int:
    if not db_path.exists():
        _print(f"DATABASE NOT FOUND: {db_path}")
        return 1
    _backup(db_path)
    return 0


def cmd_validate() -> int:
    return 0 if _validate() else 1


def cmd_migrate(db_path: Path) -> int:
    if not db_path.exists():
        _print(f"DATABASE NOT FOUND: {db_path}")
        return 1
    _backup(db_path)
    if not _validate():
        return 1
    if not _upgrade():
        _restore(db_path)
        return 1
    if not _schema_check(db_path):
        _print("SCHEMA VALIDATION FAILED")
        return 1
    return 0


def cmd_rollback(db_path: Path) -> int:
    if not db_path.exists():
        _print(f"DATABASE NOT FOUND: {db_path}")
        return 1
    return 0 if _restore(db_path) else 1


def main() -> int:
    if len(sys.argv) < 2:
        _print("USAGE: python scripts/db_guard.py [migrate|backup|validate|rollback]")
        return 2
    db_path = _resolve_db_path()
    if not db_path:
        return 2

    cmd = sys.argv[1].lower()
    if cmd == "backup":
        return cmd_backup(db_path)
    if cmd == "validate":
        return cmd_validate()
    if cmd == "rollback":
        return cmd_rollback(db_path)
    if cmd == "migrate":
        return cmd_migrate(db_path)

    _print("UNKNOWN COMMAND")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
