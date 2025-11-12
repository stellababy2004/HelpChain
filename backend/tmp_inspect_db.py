import sqlite3

p = r"C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\instance\volunteers.db"
con = sqlite3.connect(p)
c = con.cursor()
try:
    c.execute("PRAGMA table_info('admin_users')")
    rows = c.fetchall()
    print("admin_users columns:")
    for r in rows:
        print(r)
    c.execute("SELECT version_num FROM alembic_version")
    print("\nalembic_version:")
    for r in c.fetchall():
        print(r)
except Exception as e:
    print("error", e)
finally:
    con.close()
