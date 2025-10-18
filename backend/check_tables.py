#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("instance/volunteers.db")
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table";')
tables = cursor.fetchall()
print("Tables in database:", tables)
conn.close()
