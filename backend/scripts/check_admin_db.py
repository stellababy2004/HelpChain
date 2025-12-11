#!/usr/bin/env python3
"""Преглед на таблиците admin_users и users в локалната SQLite база.

Използване:
  python backend/scripts/check_admin_db.py
"""

import os
import sqlite3


def main():
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.path.join(basedir, "instance", "volunteers.db")
    if not os.path.exists(db_path):
        print("Database not found at", db_path)
        return
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    print("admin_users:")
    try:
        cur.execute("PRAGMA table_info(admin_users)")
        cols = [c[1] for c in cur.fetchall()]
        if not cols:
            print("  (table admin_users does not exist)")
        else:
            # Select all columns dynamically
            col_list = ",".join([f'"{c}"' for c in cols])
            cur.execute(f"SELECT {col_list} FROM admin_users")
            rows = cur.fetchall()
            print("  COLUMNS:", cols)
            for r in rows:
                # Prefer strict zip so we notice mismatched column/row lengths
                try:
                    print("  ", dict(zip(cols, r, strict=True)))
                except TypeError:
                    # Fallback for older Python versions or uneven rows
                    print("  ", dict(zip(cols, r, strict=False)))
    except Exception as e:
        print("Could not read admin_users:", e)

    print("\nusers:")
    try:
        cur.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cur.fetchall()]
        cur.execute("SELECT id, username, email, password_hash, role FROM users")
        rows = cur.fetchall()
        print("COLUMNS:", cols)
        for r in rows:
            print(r)
    except Exception as e:
        print("Could not read users:", e)

    con.close()


if __name__ == "__main__":
    main()
