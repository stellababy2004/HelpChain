import sys

sys.path.insert(0, "backend")

from backend.appy import app
from backend.models import AdminUser

with app.app_context():
    # Get the db instance from the app
    db = app.extensions["sqlalchemy"]

    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}, email: {admin.email}")
        print("Setting password to 'admin123'")
        admin.set_password("admin123")
        db.session.commit()
        print("Password updated successfully")
    else:
        print("Admin not found, creating...")
        admin = AdminUser(username="admin", email="admin@helpchain.live")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully")
