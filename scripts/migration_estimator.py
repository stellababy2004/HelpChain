import sqlite3
import re
from pathlib import Path

DB = "instance/app.db"


def get_table_rows(conn, table):
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def estimate():
    conn = sqlite3.connect(DB)

    migrations = Path("migrations/versions")

    for file in migrations.glob("*.py"):

        text = file.read_text()

        tables = re.findall(r"op\.add_column\(['\"](\w+)['\"]", text)

        for table in tables:
            rows = get_table_rows(conn, table)

            runtime = rows * 0.00002

            print(f"\nMigration: {file.name}")
            print(f"Table: {table}")
            print(f"Rows: {rows}")
            print(f"Estimated runtime: {runtime:.2f}s")

            if runtime > 10:
                print("⚠ Long migration detected")


if __name__ == "__main__":
    estimate()
