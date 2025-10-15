import sys

sys.path.insert(0, "backend")
from appy import app, db, AdminUser

with app.app_context():
    admins = db.session.query(AdminUser).all()
    print(f"Found {len(admins)} admin users:")
    for admin in admins:
        print(f"ID: {admin.id}, Username: {admin.username}, Email: {admin.email}")
        print(f"Password hash exists: {bool(admin.password_hash)}")
        print(f"Password check Admin123: {admin.check_password('Admin123')}")
        print("---")
