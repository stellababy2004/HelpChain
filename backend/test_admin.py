import os

from appy import AdminUser, app

with app.app_context():
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin user found: {admin.username}, email: {admin.email}")
        print(f"Password hash exists: {bool(admin.password_hash)}")
        print(
            f"Password check for {os.getenv('ADMIN_PASSWORD', 'Admin123')}: {admin.check_password(os.getenv('ADMIN_PASSWORD', 'Admin123'))}"
        )
        print(f"Password check for wrong: {admin.check_password('wrong')}")
    else:
        print("No admin user found")
