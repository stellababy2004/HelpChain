#!/usr/bin/env python3
import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

# Add helpchain_backend/src directory to Python path
helpchain_backend_dir = os.path.join(backend_dir, "helpchain-backend")
src_dir = os.path.join(helpchain_backend_dir, "src")
sys.path.insert(0, src_dir)

# Change to src directory to make relative imports work
os.chdir(src_dir)

from app import create_app, Config

app = create_app(Config)

with app.app_context():
    from models import db, AdminUser

    db.create_all()

    # Check if AdminUser table is empty and create default admin
    if AdminUser.query.count() == 0:
        admin_user = AdminUser(
            username="admin",
            email="admin@helpchain.live",
        )
        admin_user.set_password("admin123")
        db.session.add(admin_user)
        db.session.commit()
        print("AdminUser created: username=admin, password=admin123")
    else:
        print("AdminUser already exists")

    print("Database initialized successfully")
