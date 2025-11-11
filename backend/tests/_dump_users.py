import sqlite3
import pathlib

p = pathlib.Path(__file__).parent.parent / "test_local.sqlite"
print("db path", p)
if not p.exists():
    print("DB file missing")
else:
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, email FROM users")
        rows = cur.fetchall()
        print("users:", rows)
    except Exception as e:
        print("query failed", e)
    finally:
        conn.close()
