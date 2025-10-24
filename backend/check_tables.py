#!/usr/bin/env python3
import os
import sqlite3

# Use the same database path calculation as appy.py
basedir = os.path.abspath(os.path.dirname(__file__))  # backend directory
instance_dir = os.path.join(os.path.dirname(basedir), "instance")  # parent/instance
db_path = os.path.join(instance_dir, "volunteers.db")

print(f"Checking database at: {db_path}")

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table";')
tables = cursor.fetchall()
print("Tables in database:", [table[0] for table in tables])

# Check for analytics tables specifically
analytics_tables = [
    "analytics_event",
    "user_behavior",
    "performance_metrics",
    "chatbot_conversation",
]
table_names = [table[0] for table in tables]

print("\nAnalytics tables:")
for table in analytics_tables:
    if table in table_names:
        print(f"  ✅ {table}")
    else:
        print(f"  ❌ {table}")

conn.close()
