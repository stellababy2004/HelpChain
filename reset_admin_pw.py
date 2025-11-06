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
        admin.set_password("Admin123")
        from backend.extensions import db

        db.session.commit()
        print("Admin password reset to Admin123")
    else:
        print("Admin user not found")
