import sqlite3
import subprocess
import sys
from pathlib import Path

DB_PATH = Path("instance/helpchain.db")

def cleanup_tmp_tables():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE '_alembic_tmp_%'
    """)

    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        print("No leftover Alembic temp tables.")
        conn.close()
        return

    print("Cleaning Alembic temp tables:")

    for table in tables:
        print("  dropping", table)
        cur.execute(f"DROP TABLE {table}")

    conn.commit()
    conn.close()

    print("Cleanup complete.\n")


def check_revision():
    try:
        out = subprocess.check_output(
            ["flask", "db", "current"],
            stderr=subprocess.STDOUT,
            text=True
        )
        print("Current revision:")
        print(out)
    except Exception as e:
        print("Could not check revision:", e)


def run_upgrade():
    print("\nRunning migration upgrade...\n")

    try:
        subprocess.check_call(["flask", "db", "upgrade"])
    except subprocess.CalledProcessError:
        print("\nMigration failed again.")
        sys.exit(1)


def main():
    print("=== HelpChain Migration Recovery Guard ===\n")

    cleanup_tmp_tables()
    check_revision()
    run_upgrade()

    print("\nMigration finished.\n")


if __name__ == "__main__":
    main()
