import os
import sys

sys.path.insert(0, "backend")

# Import both model files to resolve dependencies
from flask import Flask
from models import AdminUser, db
from models_with_analytics import Task  # Import Task to resolve Volunteer relationship
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'instance', 'volunteers.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    admin = db.session.query(AdminUser).filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}")
        print(f"Password hash: {admin.password_hash}")
        print(f"Check Admin123: {admin.check_password('Admin123')}")

        # Test manual hash
        test_hash = generate_password_hash("Admin123")
        print(f"Manual hash: {test_hash}")
        print(f"Check manual hash: {check_password_hash(test_hash, 'Admin123')}")
        print(
            f"Check against stored: {check_password_hash(admin.password_hash, 'Admin123')}"
        )
    else:
        print("No admin found")

app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'instance', 'volunteers.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    admin = db.session.query(AdminUser).filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}")
        print(f"Password hash: {admin.password_hash}")
        print(f"Check Admin123: {admin.check_password('Admin123')}")

        # Test manual hash
        test_hash = generate_password_hash("Admin123")
        print(f"Manual hash: {test_hash}")
        print(f"Check manual hash: {check_password_hash(test_hash, 'Admin123')}")
        print(
            f"Check against stored: {check_password_hash(admin.password_hash, 'Admin123')}"
        )
    else:
        print("No admin found")
