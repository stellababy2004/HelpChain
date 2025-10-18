#!/usr/bin/env python3

"""
Обновяване на базата данни с новия Feedback модел
"""

from appy import app, db


def update_database():
    """Създава новите таблици в базата данни"""
    with app.app_context():
        try:
            print("🔄 Обновявам базата данни с Feedback модел...")

            # Създаваме всички таблици (вкл. новия Feedback)
            db.create_all()

            print("✅ Базата данни е обновена успешно!")
            print("📋 Създадена е таблица 'feedback' за съхранение на обратни връзки")

        except Exception as e:
            print(f"❌ Грешка при обновяване на базата данни: {str(e)}")
            return False

        return True


if __name__ == "__main__":
    update_database()
