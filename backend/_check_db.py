import os
import sqlite3

db = "test_local.sqlite"
print("exists:", os.path.exists(db))
conn = sqlite3.connect(db)
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("tables:", [r[0] for r in cur.fetchall()])
conn.close()
