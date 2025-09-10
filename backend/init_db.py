from appy import app
from models import db  # <-- добави този ред!

with app.app_context():
    db.create_all()
    print("Базата е създадена успешно!")
