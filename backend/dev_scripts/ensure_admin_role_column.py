import sqlite3

p = r"C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\instance\volunteers.db"
con = sqlite3.connect(p)
c = con.cursor()
try:
    c.execute("PRAGMA table_info('admin_users')")
    cols = [r[1] for r in c.fetchall()]
    print("existing cols:", cols)
    if "role" not in cols:
        print("Adding role column to admin_users")
        c.execute("ALTER TABLE admin_users ADD COLUMN role VARCHAR(64)")
        con.commit()
        print("role column added")
    else:
        print("role column already present")
except Exception as e:
    print("error", e)
finally:
    con.close()
