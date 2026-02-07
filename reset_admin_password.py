from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import User
from werkzeug.security import generate_password_hash

USERNAME = "admin"
EMAIL = "admin@helpchain.local"
NEW_PASSWORD = "Admin-2026!ChangeMe"

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
