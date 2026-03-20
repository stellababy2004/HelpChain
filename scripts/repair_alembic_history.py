import sqlite3

DB = "instance/app.db"


def repair():

    conn = sqlite3.connect(DB)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    tmp_tables = [t[0] for t in tables if t[0].startswith("_alembic_tmp_")]

    for t in tmp_tables:
        print(f"Removing temp table {t}")
        conn.execute(f"DROP TABLE {t}")

    conn.commit()
    conn.close()

    print("✔ alembic history repaired")


if __name__ == "__main__":
    repair()
