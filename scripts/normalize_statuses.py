"""
Quick normalize statuses script.

Usage:
  set DATABASE_URL env var (or pass as first arg):
    export DATABASE_URL="sqlite:///c:/dev/HelpChain/HelpChain.bg/instance/helpchain.db"
    python normalize_statuses.py
  or
    python normalize_statuses.py sqlite:///c:/path/to/db.sqlite
"""
import os
import sys
from sqlalchemy import create_engine, text

url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL")
if not url:
    print("Provide DATABASE_URL env or as first arg (e.g. sqlite:///c:/path/to/db.sqlite)")
    sys.exit(1)

engine = create_engine(url, future=True)

# Adjust table/column names if different
TABLE = "request"
STATUS_COL = "status"

# SQL variants
SQL_UPDATES = [
    # map French -> canonical codes
    f"UPDATE {TABLE} SET {STATUS_COL}='pending' WHERE {STATUS_COL} IN ('Inconnu','En attente')",
    f"UPDATE {TABLE} SET {STATUS_COL}='in_progress' WHERE {STATUS_COL} IN ('En cours')",
    # optional: normalize common english display labels to codes
    f"UPDATE {TABLE} SET {STATUS_COL}='in_progress' WHERE LOWER({STATUS_COL}) IN ('in progress')",
    f"UPDATE {TABLE} SET {STATUS_COL}='pending' WHERE LOWER({STATUS_COL}) IN ('pending')",
]

with engine.connect() as conn:
    trans = conn.begin()
    try:
        for sql in SQL_UPDATES:
            res = conn.execute(text(sql))
            print(f"Executed: {sql} -- affected: {res.rowcount}")
        trans.commit()
        print("Status normalization completed.")
    except Exception as e:
        trans.rollback()
        print("Error, transaction rolled back:", e)
        raise
