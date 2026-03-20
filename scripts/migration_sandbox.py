from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import sys
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
    if not env.get("SQLALCHEMY_DATABASE_URI") and not env.get("DATABASE_URL"):
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


def _sandbox_path(db_path: Path) -> Path:
    sandbox_dir = db_path.parent / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    return sandbox_dir / f"{db_path.stem}_sandbox.db"


def _copy_to_sandbox(db_path: Path, sandbox_path: Path) -> None:
    if sandbox_path.exists():
        # Never overwrite existing sandbox
        idx = 1
        while True:
            candidate = sandbox_path.with_name(
                f"{sandbox_path.stem}_{idx}{sandbox_path.suffix}"
            )
            if not candidate.exists():
                sandbox_path = candidate
                break
            idx += 1
    shutil.copy2(db_path, sandbox_path)
    _print("SANDBOX CREATED")
    _print(str(sandbox_path))


def _run_flask_cmd(args: list[str], env_override: dict[str, str] | None = None) -> int:
    cmd = [sys.executable, "-m", "flask", "--app", "backend.appy:app"] + args
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


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
    _print("SCHEMA VALIDATION PASSED")
    return True


def cmd_sandbox(db_path: Path) -> int:
    if not db_path.exists():
        _print(f"DATABASE NOT FOUND: {db_path}")
        return 1
    sandbox_path = _sandbox_path(db_path)
    _copy_to_sandbox(db_path, sandbox_path)
    return 0


def cmd_validate(db_path: Path) -> int:
    sandbox_path = _sandbox_path(db_path)
    if not sandbox_path.exists():
        _print("SANDBOX NOT FOUND")
        return 1
    return 0 if _schema_check(sandbox_path) else 1


def cmd_migrate(db_path: Path) -> int:
    if not db_path.exists():
        _print(f"DATABASE NOT FOUND: {db_path}")
        return 1

    sandbox_path = _sandbox_path(db_path)
    _copy_to_sandbox(db_path, sandbox_path)

    env_override = {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{sandbox_path}"}
    if _run_flask_cmd(["db", "upgrade"], env_override=env_override) != 0:
        _print("SANDBOX MIGRATION FAILED")
        _print("REAL DATABASE NOT MODIFIED")
        return 1

    _print("SANDBOX MIGRATION SUCCESS")
    if not _schema_check(sandbox_path):
        _print("REAL DATABASE NOT MODIFIED")
        return 1

    _print("APPLYING MIGRATION TO REAL DATABASE")
    if _run_flask_cmd(["db", "upgrade"]) != 0:
        _print("MIGRATION FAILED ON REAL DATABASE")
        return 1

    _print("DONE")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        _print("USAGE: python scripts/migration_sandbox.py [migrate|sandbox|validate]")
        return 2

    db_path = _resolve_db_path()
    if not db_path:
        return 2

    cmd = sys.argv[1].lower()
    if cmd == "sandbox":
        return cmd_sandbox(db_path)
    if cmd == "validate":
        return cmd_validate(db_path)
    if cmd == "migrate":
        return cmd_migrate(db_path)

    _print("UNKNOWN COMMAND")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
