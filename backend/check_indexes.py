#!/usr/bin/env python3
"""
Script to check existing database indexes
"""
from appy import app, db

with app.app_context():
    # Get all indexes
    result = db.session.execute(
        db.text(
            'SELECT name, tbl_name, sql FROM sqlite_master WHERE type="index" AND name NOT LIKE "sqlite_%"'
        )
    )
    indexes = result.fetchall()

    print("Съществуващи индекси в базата данни:")
    print("=" * 50)
    for idx in indexes:
        print(f"Индекс: {idx[0]}")
        print(f"Таблица: {idx[1]}")
        if idx[2]:
            print(f"SQL: {idx[2][:100]}...")
        print("-" * 30)

    print(f"Общо индекси: {len(indexes)}")

    # Check for specific tables
    tables_to_check = [
        "users",
        "admin_users",
        "volunteers",
        "help_requests",
        "tasks",
        "notifications",
    ]
    print("\nПроверка по таблици:")
    print("=" * 30)
    for table in tables_to_check:
        table_indexes = [idx for idx in indexes if idx[1] == table]
        print(f"{table}: {len(table_indexes)} индекса")
        for idx in table_indexes:
            print(f"  - {idx[0]}")
