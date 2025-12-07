import sqlite3


def main():
    try:
        with sqlite3.connect("instance/volunteers.db") as conn:
            c = conn.cursor()

            # Провери дали таблицата съществува
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='volunteers'")
            if not c.fetchone():
                print("Таблица 'volunteers' не съществува.")
                return

            # Брой доброволци
            c.execute("SELECT COUNT(*) FROM volunteers")
            count = c.fetchone()[0]
            print(f"Брой доброволци: {count}")

            # Първи 5 имейла
            c.execute("SELECT email FROM volunteers LIMIT 5")
            emails = c.fetchall()
            print("Първи 5 имейла:")
            for email in emails:
                print(email[0])
    except sqlite3.Error as e:
        print(f"Грешка в базата данни: {e}")


if __name__ == "__main__":
    main()
