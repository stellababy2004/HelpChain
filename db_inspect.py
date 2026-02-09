import sqlite3

db = r"C:\dev\HelpChain\HelpChain.bg\instance\app.db"

con = sqlite3.connect(db)
cur = con.cursor()

print("DB:", db)
print("Tables:")

for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall():
    print(" -", name)

con.close()
