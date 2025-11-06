import os
import sqlite3

db_path = os.path.join("instance", "volunteers.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = c.fetchall()
    print("Tables:", tables)
    for table in tables:
        if "admin" in table[0].lower():
            print(f"Checking table: {table[0]}")
            try:
                c.execute(f"PRAGMA table_info({table[0]})")
                columns = c.fetchall()
                print(f"Columns in {table[0]}:", columns)
                c.execute(f"SELECT * FROM {table[0]}")
                rows = c.fetchall()
                print(f"Rows in {table[0]}:", rows)
            except Exception as e:
                print(f"Error checking {table[0]}: {e}")
    conn.close()
else:
    print("Database not found")
