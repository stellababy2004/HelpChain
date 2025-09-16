import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.appy import app, db
from backend.models import User
from werkzeug.security import generate_password_hash
from datetime import datetime

EMAIL = "testuser@example.com"
PASSWORD = "Str0ng!Passw0rd#2025"

with app.app_context():
    if not User.query.filter_by(email=EMAIL).first():
        user = User(
            username="test user",
            email=EMAIL,
            password=generate_password_hash(PASSWORD),
            role="volunteer",
            created_at=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.commit()
        print("created", EMAIL, "password:", PASSWORD)
    else:
        print("already exists:", EMAIL)
