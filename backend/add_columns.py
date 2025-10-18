#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()

# Add missing columns
cursor.execute('ALTER TABLE feedback ADD COLUMN user_type VARCHAR(20) DEFAULT "guest"')
cursor.execute("ALTER TABLE feedback ADD COLUMN user_id INTEGER")
cursor.execute("ALTER TABLE feedback ADD COLUMN page_url VARCHAR(500)")
cursor.execute("ALTER TABLE feedback ADD COLUMN user_agent VARCHAR(500)")
cursor.execute("ALTER TABLE feedback ADD COLUMN ip_address VARCHAR(45)")

conn.commit()
conn.close()
print("Missing columns added successfully!")
