import sqlite3

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()

# Get tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

# Get columns for each table
for table in tables:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print(f"{table} columns:", [col[1] for col in columns])

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table} rows:", count)

conn.close()
