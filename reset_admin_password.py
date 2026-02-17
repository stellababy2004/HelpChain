import os

from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.models import User

# Security: never hardcode credentials in tracked files (GitGuardian will block).
USERNAME = os.getenv("ADMIN_USERNAME")
EMAIL = os.getenv("ADMIN_EMAIL")
NEW_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not NEW_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD not set in environment")
if not USERNAME and not EMAIL:
    raise RuntimeError("Set ADMIN_USERNAME and/or ADMIN_EMAIL in environment")

app = create_app()

with app.app_context():
    user = User.query.filter(
        (User.username == USERNAME) | (User.email == EMAIL)
    ).first()

    if not user:
        user = User(username=USERNAME, email=EMAIL)
        db.session.add(user)

    user.password_hash = generate_password_hash(NEW_PASSWORD)
    user.role = "admin"
    user.is_active = True

    db.session.commit()

    print("OK admin reset:")
    print(" id =", user.id)
    print(" username =", user.username)
    print(" email =", user.email)
    print(" role =", user.role)
    print(" active =", user.is_active)
