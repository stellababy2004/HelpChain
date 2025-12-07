import os
import sqlite3

DB = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "instance", "volunteers.db"
)
print("DB path ->", os.path.abspath(DB))
if not os.path.exists(DB):
    print("DB file not found")
    raise SystemExit(0)
conn = sqlite3.connect(DB)
cur = conn.cursor()
print("Tables:")
for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall():
    print(" -", r[0])

print("\nadmin_users:")
try:
    for row in cur.execute("SELECT id,username,email FROM admin_users").fetchall():
        print(row)
except Exception as e:
    print("  error:", e)

print("\nusers:")
try:
    for row in cur.execute(
        "SELECT id,username,email,role,password_hash FROM users"
    ).fetchall():
        print(row)
except Exception as e:
    print("  error:", e)

conn.close()
