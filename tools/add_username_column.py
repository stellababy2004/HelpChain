from sqlalchemy import text
from backend.appy import app, db

with app.app_context():
    try:
        # Добавяме колоната с default празен стринг, за да не счупим вече записаните редове
        db.session.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100) DEFAULT ''"))
        db.session.commit()
        print("Колоната 'username' е добавена успешно.")
    except Exception as e:
        print("Грешка при добавяне на колоната:", e)