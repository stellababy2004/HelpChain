#!/usr/bin/env python3
"""Check admin password"""

import os
import sys

# Add paths
backend_dir = os.path.dirname(__file__)
sys.path.insert(0, backend_dir)

from appy import app, db, AdminUser

with app.app_context():
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print("Admin exists")
        print("Password check for Admin123:", admin.check_password("Admin123"))
    else:
        print("Admin user not found")