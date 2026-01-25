import sqlite3

db = r"C:\dev\HelpChain\HelpChain.bg\instance\app.db"
con = sqlite3.connect(db)
cur = con.cursor()

rows = cur.execute("""
SELECT status, COUNT(*) 
FROM requests
GROUP BY status
ORDER BY COUNT(*) DESC
""").fetchall()

print("DB:", db)
print("Status counts in requests:")
for status, cnt in rows:
    print(f" - {status!r}: {cnt}")

con.close()
