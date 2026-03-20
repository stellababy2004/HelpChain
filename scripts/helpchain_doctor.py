import sys
import sqlite3
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.local_db_guard import APP_IMPORT_PATH, select_local_runtime_db

SELECTION = select_local_runtime_db()
DB_PATH = SELECTION.selected_path

checks = []


def check(name, fn):
    try:
        fn()
        checks.append((name, "OK"))
    except Exception as e:
        checks.append((name, f"FAIL: {e}"))


def check_db_exists():
    if DB_PATH is None:
        raise RuntimeError("no supported sqlite runtime DB selected")
    if not DB_PATH.exists():
        raise RuntimeError(f"runtime DB missing: {DB_PATH}")


def check_tables():
    if DB_PATH is None:
        raise RuntimeError("no supported sqlite runtime DB selected")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables = {
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    required = {
        "users",
        "requests",
        "admin_users",
        "volunteers",
    }

    missing = required - tables
    if missing:
        raise RuntimeError(f"missing tables: {missing}")


def check_admin():
    if DB_PATH is None:
        raise RuntimeError("no supported sqlite runtime DB selected")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    res = cur.execute(
        "SELECT username FROM admin_users LIMIT 1"
    ).fetchone()

    if not res:
        raise RuntimeError("no admin user present")


def check_health():
    urls = (
        "http://127.0.0.1:5000/health",
        "http://127.0.0.1:5005/health",
    )
    for url in urls:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            continue
    raise RuntimeError("server not running or health endpoint unreachable")


def main():
    print(f"APP: {APP_IMPORT_PATH}")
    print(f"DB selected: {SELECTION.selected_uri}")
    print(f"DB selector: {SELECTION.reason}")
    check("DB file exists", check_db_exists)
    check("Core tables", check_tables)
    check("Admin user", check_admin)
    check("Health endpoint", check_health)

    print("")
    print("HelpChain Doctor Report")
    print("----------------------")

    failed = False

    for name, result in checks:
        print(f"{name:25} {result}")
        if result.startswith("FAIL"):
            failed = True

    print("")

    if failed:
        print("STATUS: SYSTEM NOT HEALTHY")
        sys.exit(1)

    print("STATUS: SYSTEM HEALTHY")
    sys.exit(0)


if __name__ == "__main__":
    main()
