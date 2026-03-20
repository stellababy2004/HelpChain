from __future__ import annotations

import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_DB = ROOT / "instance" / "hc_local_dev.db"
FALLBACK_DB = ROOT / "backend" / "instance" / "app_clean.db"
REQUIRED_TABLES = ("admin_users", "structures", "users", "cases")


def _read_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return {}
    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _resolve_db_uri() -> str:
    env = _read_env_file()
    env.update({k: v for k, v in os.environ.items() if v})

    raw = (
        env.get("SQLALCHEMY_DATABASE_URI")
        or env.get("DATABASE_URL")
        or env.get("HC_DB_PATH")
        or ""
    ).strip()

    if not raw:
        return f"sqlite:///{PRIMARY_DB.as_posix()}"
    if "://" not in raw:
        return f"sqlite:///{Path(raw).resolve().as_posix()}"
    return raw


def _resolve_db_path(uri: str) -> Path | None:
    if not uri.startswith("sqlite:"):
        return None
    raw = uri.replace("sqlite:///", "", 1).replace("sqlite://", "", 1).replace("\\", "/")
    path = Path(raw)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def _inspect_db(db_path: Path) -> dict[str, object]:
    info: dict[str, object] = {
        "path": db_path,
        "exists": db_path.exists(),
        "tables": set(),
        "admin_count": 0,
        "healthy": False,
    }
    if not info["exists"]:
        return info

    con = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in con.execute("select name from sqlite_master where type='table'")}
        admin_count = 0
        if "admin_users" in tables:
            admin_count = int(con.execute("select count(*) from admin_users").fetchone()[0])
    finally:
        con.close()

    healthy = all(table in tables for table in REQUIRED_TABLES) and admin_count > 0
    info["tables"] = tables
    info["admin_count"] = admin_count
    info["healthy"] = healthy
    return info


def _print_section(title: str, uri: str, info: dict[str, object]) -> None:
    tables = info["tables"]
    admin_count = int(info["admin_count"])

    print(title)
    print(f"DB selected: {uri}")
    print(f"File exists: {_yes_no(bool(info['exists']))}")
    for table in REQUIRED_TABLES:
        print(f"{table}: {_yes_no(table in tables)}")
    print(f"admin account exists: {_yes_no(admin_count > 0)}")
    print("")


def main() -> int:
    selected_uri = _resolve_db_uri()
    selected_path = _resolve_db_path(selected_uri)

    print("HelpChain DB Preflight")
    print("----------------------")

    if selected_path is None:
        print(f"DB selected: {selected_uri}")
        print("RESULT: REFUSE START")
        print("Reason: unsupported DB URI for local sqlite preflight")
        return 1

    primary_info = _inspect_db(selected_path)
    _print_section("Primary DB", selected_uri, primary_info)

    fallback_info = primary_info
    if selected_path.resolve() != FALLBACK_DB.resolve():
        fallback_uri = f"sqlite:///{FALLBACK_DB.as_posix()}"
        fallback_info = _inspect_db(FALLBACK_DB)
        _print_section("Fallback DB", fallback_uri, fallback_info)

    if bool(primary_info["healthy"]):
        print("RESULT: SAFE TO START")
        return 0

    if bool(fallback_info["healthy"]):
        print("RESULT: FALLBACK DB USED")
        return 0

    print("RESULT: REFUSE START")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
