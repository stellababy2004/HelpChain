import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from backend.appy import app
from backend.models import AdminUser

with app.app_context():
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        admin.set_password("test-password")
        from backend.extensions import db

        db.session.commit()
        print("Admin password reset to test-password")
    else:
        print("Admin user not found")

