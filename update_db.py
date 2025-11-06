import os
import sqlite3

# Path to the database
db_path = os.path.join(os.path.dirname(__file__), "instance", "volunteers.db")

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add missing columns to admin_users table
alter_statements = [
    "ALTER TABLE admin_users ADD COLUMN role TEXT DEFAULT 'moderator';",
    "ALTER TABLE admin_users ADD COLUMN backup_codes TEXT;",
    "ALTER TABLE admin_users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0;",
    "ALTER TABLE admin_users ADD COLUMN last_login DATETIME;",
    "ALTER TABLE admin_users ADD COLUMN is_active BOOLEAN DEFAULT 1;",
    "ALTER TABLE admin_users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;",
    "ALTER TABLE admin_users ADD COLUMN locked_until DATETIME;",
]

for stmt in alter_statements:
    try:
        cursor.execute(stmt)
        print(f"Executed: {stmt}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column already exists: {stmt}")
        else:
            print(f"Error executing {stmt}: {e}")

conn.commit()
conn.close()
print("Database schema updated successfully.")
