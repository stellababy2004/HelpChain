#!/usr/bin/env python3
"""
Reset admin password to Admin123
"""
import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app, db, AdminUser


def reset_admin_password():
    with app.app_context():
        admin_user = db.session.query(AdminUser).filter_by(username="admin").first()
        if not admin_user:
            print("Admin user not found")
            return

        print(f"Admin user found: {admin_user.username}")
        print(f"Current password hash: {admin_user.password_hash}")

        # Reset password to Admin123
        admin_user.set_password("Admin123")
        db.session.commit()

        print(f"Password reset successful")
        print(f"New password hash: {admin_user.password_hash}")

        # Verify it works
        from werkzeug.security import check_password_hash

        result = check_password_hash(admin_user.password_hash, "Admin123")
        print(f"Password verification: {result}")


if __name__ == "__main__":
    reset_admin_password()
