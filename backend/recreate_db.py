#!/usr/bin/env python3
"""
Пресъздаване на базата данни от нулата
"""

import os

from appy import app, db


def recreate_database():
    """Пресъздава базата данни напълно от нулата"""
    with app.app_context():
        # Проверяваме дали има база данни файлове
        db_paths = [
            "instance/site.db",
            "instance/volunteers.db",
            "instance/helpchain.db",
        ]

        for db_path in db_paths:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print(f"✅ Изтрит файл: {db_path}")
                except Exception as e:
                    print(f"⚠️ Грешка при изтриване на {db_path}: {e}")

        # Създаваме всички таблици от нулата
        db.drop_all()
        db.create_all()

        print("✅ База данни пресъздадена успешно!")

        # Проверяваме създадените таблици using a context-managed connection
        from sqlalchemy import inspect

        with db.engine.connect() as _conn:
            inspector = inspect(_conn)
            tables = inspector.get_table_names()
            print(f"📊 Създадени таблици: {tables}")

            # Проверяваме колони в volunteers таблицата
            if "volunteers" in tables:
                columns = [col["name"] for col in inspector.get_columns("volunteers")]
                print(f"👥 Колони в volunteers: {columns}")


if __name__ == "__main__":
    recreate_database()
