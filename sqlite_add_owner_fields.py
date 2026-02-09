import sqlite3
from pathlib import Path

db_path = Path("instance/app.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# add columns if missing
cur.execute("PRAGMA table_info(requests);")
cols = {row[1] for row in cur.fetchall()}

if "owner_id" not in cols:
    cur.execute("ALTER TABLE requests ADD COLUMN owner_id INTEGER;")

if "owned_at" not in cols:
    cur.execute("ALTER TABLE requests ADD COLUMN owned_at DATETIME;")

conn.commit()
conn.close()
print("OK: owner_id + owned_at added (or already existed).")
