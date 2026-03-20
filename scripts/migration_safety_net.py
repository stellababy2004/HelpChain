import sqlite3
import subprocess
import shutil
from pathlib import Path
import sys

DB_PATH = Path("instance/helpchain.db")
TEST_DB = Path("instance/helpchain_test.db")


def print_header(title):
    print("\n=== " + title + " ===")


def check_tmp_tables():
    print_header("Checking Alembic temp tables")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE '_alembic_tmp_%'
    """)

    tables = [r[0] for r in cur.fetchall()]
    conn.close()

    if tables:
        print("Temp tables detected:")
        for t in tables:
            print("  ", t)
        print("Run recovery guard before migration.")
        sys.exit(1)

    print("OK")


def check_revision():
    print_header("Checking migration revision")

    out = subprocess.check_output(
        ["flask", "db", "current"],
        text=True
    )

    print(out.strip())


def run_drift_detector():
    print_header("Running drift detector")

    try:
        subprocess.check_call(
            ["python", "scripts/migration_drift_detector.py"]
        )
    except subprocess.CalledProcessError:
        print("Drift detected. Fix schema before migrating.")
        sys.exit(1)


def clone_database():
    print_header("Cloning database for dry run")

    if TEST_DB.exists():
        TEST_DB.unlink()

    shutil.copy(DB_PATH, TEST_DB)

    print("Test DB created:", TEST_DB)


def run_dry_upgrade():
    print_header("Running migration on test DB")

    env = dict(**subprocess.os.environ)
    env["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{TEST_DB}"

    try:
        subprocess.check_call(
            ["flask", "db", "upgrade"],
            env=env
        )
    except subprocess.CalledProcessError:
        print("Migration FAILED on test DB.")
        sys.exit(1)

    print("Dry-run migration OK")


def main():
    print("\nHelpChain Migration Safety Net\n")

    check_tmp_tables()
    check_revision()
    run_drift_detector()
    clone_database()
    run_dry_upgrade()

    print("\nSafety checks passed. You can run real migration.\n")


if __name__ == "__main__":
    main()
