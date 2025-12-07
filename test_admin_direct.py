import os

from backend.appy import app

print("App created successfully")
with app.app_context():
    print("App context entered")
    from backend.models import AdminUser

    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}")
        print(f"Password check {os.getenv('ADMIN_PASSWORD', 'Admin123')}: {admin.check_password(os.getenv('ADMIN_PASSWORD', 'Admin123'))}")
        print(f"Password check admin123: {admin.check_password('admin123')}")
    else:
        print("No admin found")
