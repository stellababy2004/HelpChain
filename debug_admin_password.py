#!/usr/bin/env python3
"""
Script to debug and reset admin password for HelpChain analytics testing
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from flask import Flask

from backend.models import AdminUser, db


def debug_admin_password():
    """Debug admin password setup"""
    print("=== Admin Password Debug ===")

    # Check environment variable
    admin_password_env = os.getenv("ADMIN_PASSWORD")
    print(f"ADMIN_PASSWORD env var: {admin_password_env}")

    # Create Flask app context
    app = Flask(__name__)

    # Database configuration
    instance_path = os.path.join(os.path.dirname(__file__), "instance")
    os.makedirs(instance_path, exist_ok=True)
    db_path = os.path.join(instance_path, "volunteers.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        # Check database
        db.create_all()

        # Check if admin user exists
        admin_user = AdminUser.query.filter_by(username="admin").first()
        if admin_user:
            print(f"Admin user exists: {admin_user.username}")
            print(f"Admin user ID: {admin_user.id}")
            print(f"Password hash exists: {bool(admin_user.password_hash)}")

            # Test password verification
            test_passwords = ["Admin123", "admin123", "admin", "Admin123!"]
            for pwd in test_passwords:
                is_valid = admin_user.check_password(pwd)
                print(f"Password '{pwd}' valid: {is_valid}")
        else:
            print("Admin user does not exist!")

        # Reset admin password
        print("\n=== Resetting Admin Password ===")
        if admin_user:
            admin_user.set_password("Admin123")
            db.session.commit()
            print("Admin password reset to 'Admin123'")

            # Verify reset
            is_valid = admin_user.check_password("Admin123")
            print(f"Password reset verification: {is_valid}")
        else:
            # Create new admin user
            admin_user = AdminUser(username="admin")
            admin_user.set_password("Admin123")
            db.session.add(admin_user)
            db.session.commit()
            print("New admin user created with password 'Admin123'")


if __name__ == "__main__":
    debug_admin_password()
