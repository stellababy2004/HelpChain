import os
import sqlite3

db_path = os.path.join("..", "instance", "volunteers.db")
print("DB path:", db_path)
print("Exists:", os.path.exists(db_path))

if os.path.exists(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
        tables = cursor.fetchall()
        print("Tables:", tables)

        if ("volunteers",) in tables:
            cursor.execute("SELECT COUNT(*) FROM volunteers")
            count = cursor.fetchone()[0]
            print(f"Volunteers count: {count}")

            # Get first few volunteers
            cursor.execute("SELECT id, name, email FROM volunteers LIMIT 3")
            volunteers = cursor.fetchall()
            print("Sample volunteers:", volunteers)
else:
    print("Database not found")
