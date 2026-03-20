import sqlite3

DB = "instance/app.db"


def cleanup():

    conn = sqlite3.connect(DB)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    for t in tables:
        name = t[0]

        if name.startswith("_alembic_tmp_"):
            print(f"Removing orphan table {name}")
            conn.execute(f"DROP TABLE {name}")

    conn.commit()
    conn.close()

    print("✔ cleanup done")


if __name__ == "__main__":
    cleanup()
