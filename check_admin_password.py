#!/usr/bin/env python3
"""
Check admin password hash in database
"""

import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app, db, AdminUser  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402


def check_admin_password():
    with app.app_context():
        admin_user = db.session.query(AdminUser).filter_by(username="admin").first()
        if not admin_user:
            print("Admin user not found")
            return

        print(f"Admin user: {admin_user.username}")
        print(f"Password hash: {admin_user.password_hash}")

        # Test different passwords
        test_passwords = ["Admin123", "admin123", "admin", "Admin", "123"]

        for password in test_passwords:
            result = check_password_hash(admin_user.password_hash, password)
            print(f"Password '{password}': {result}")

        # Show what the hash should be for Admin123
        correct_hash = generate_password_hash("Admin123")
        print(f"Correct hash for Admin123: {correct_hash}")
        print(
            f"Current hash matches correct: {admin_user.password_hash == correct_hash}"
        )


if __name__ == "__main__":
    check_admin_password()
