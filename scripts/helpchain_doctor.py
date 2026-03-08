import sys
import sqlite3
import requests
from pathlib import Path

DB_PATH = Path("backend/instance/app_clean.db")

checks = []


def check(name, fn):
    try:
        fn()
        checks.append((name, "OK"))
    except Exception as e:
        checks.append((name, f"FAIL: {e}"))


def check_db_exists():
    if not DB_PATH.exists():
        raise RuntimeError("canonical DB missing")


def check_tables():
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    res = cur.execute(
        "SELECT username FROM admin_users LIMIT 1"
    ).fetchone()

    if not res:
        raise RuntimeError("no admin user present")


def check_health():
    try:
        r = requests.get("http://127.0.0.1:5005/health", timeout=2)
        if r.status_code != 200:
            raise RuntimeError(f"health returned {r.status_code}")
    except Exception:
        raise RuntimeError("server not running or health endpoint unreachable")


def main():
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
