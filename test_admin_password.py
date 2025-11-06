import os
import sys

# Add paths
sys.path.insert(0, "backend")
sys.path.insert(0, "backend/helpchain-backend/src")

# Set environment
os.environ["FLASK_APP"] = "backend/appy.py"

# Import Flask app and models
from flask import Flask

from backend.extensions import db as db_ext
from backend.models import AdminUser, db

# Create a minimal app for testing
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    r"sqlite:///C:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\instance\volunteers.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "test-key"  # pragma: allowlist secret

db_ext.init_app(app)

with app.app_context():
    admin = db.session.query(AdminUser).filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}")
        print(f"Password hash exists: {bool(admin.password_hash)}")
        if admin.password_hash:
            print(f"Password hash: {admin.password_hash[:20]}...")
        print(
            f"Password check {os.getenv('ADMIN_PASSWORD', 'Admin123')}: {admin.check_password(os.getenv('ADMIN_PASSWORD', 'Admin123'))}"
        )
        print(f"Password check admin123: {admin.check_password('admin123')}")
        print(f"Password check Admin: {admin.check_password('Admin')}")
    else:
        print("Admin not found")
