import os
import sqlite3

path = r"C:\dev\HelpChain\HelpChain.bg\instance\app.db"
print("DB exists:", os.path.exists(path), "size:", os.path.getsize(path) if os.path.exists(path) else None)
con = sqlite3.connect(path)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rows = cur.fetchall()
print("SQLite tables:", [r[0] for r in rows])
con.close()
