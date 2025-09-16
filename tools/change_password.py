import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.appy import app, db
from backend.models import User
from werkzeug.security import generate_password_hash

EMAIL = "vikisk@yahoo.fr"  # смени имейла
NEW_PASSWORD = "N3w$ecurePass!2025"  # смени паролата

with app.app_context():
    u = User.query.filter_by(email=EMAIL).first()
    if not u:
        print("user not found:", EMAIL)
    else:
        u.password = generate_password_hash(NEW_PASSWORD)
        db.session.commit()
        print("updated password for", EMAIL)
