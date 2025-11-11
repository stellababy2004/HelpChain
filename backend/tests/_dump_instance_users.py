import sqlite3
import pathlib

p = pathlib.Path(__file__).parent.parent / "instance" / "volunteers.db"
print("db path", p)
if not p.exists():
    print("missing")
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
