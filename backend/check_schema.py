#!/usr/bin/env python3
import sqlite3
import os

# Use the same database path as appy.py
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(os.path.dirname(basedir), "instance")
db_path = os.path.join(instance_dir, "volunteers.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check all analytics tables
tables = ['analytics_events', 'user_behaviors', 'performance_metrics', 'chatbot_conversations']

for table in tables:
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print(f'\n{table} table schema:')
        for col in columns:
            print(f'  {col[1]} - {col[2]}')
    except Exception as e:
        print(f'\nError checking {table}: {e}')

conn.close()