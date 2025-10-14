import sys
import os

sys.path.insert(0, "backend")

from backend.appy import app
from backend.models import AdminUser

with app.app_context():
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}, email: {admin.email}")
        print("Setting password to 'admin123'")
        admin.set_password("admin123")
        app.db.session.commit()
        print("Password updated successfully")
    else:
        print("Admin not found, creating...")
        admin = AdminUser(username="admin", email="admin@helpchain.live")
        admin.set_password("admin123")
        app.db.session.add(admin)
        app.db.session.commit()
        print("Admin created successfully")
