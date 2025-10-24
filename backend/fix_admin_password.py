#!/usr/bin/env python3
"""Fix admin password script"""

import os
import sys

# Add paths
backend_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(backend_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, parent_dir)

from appy import app, db, AdminUser

with app.app_context():
    # Ensure database is created
    db.create_all()

    # Check admin user
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print("Admin exists, checking password...")
        expected_password = os.getenv("ADMIN_PASSWORD", "Admin123")
        password_valid = admin.check_password(expected_password)
        print(f"Password check for {expected_password}: {password_valid}")

        if not password_valid:
            print("Updating password...")
            admin.set_password(expected_password)
            db.session.commit()
            print("Password updated successfully")
            print(f"New password check: {admin.check_password(expected_password)}")
    else:
        print("Creating admin user...")
        admin = AdminUser(username="admin", email="admin@helpchain.live")
        admin.set_password(os.getenv("ADMIN_PASSWORD", "Admin123"))
        db.session.add(admin)
        db.session.commit()
        print("Admin user created")
