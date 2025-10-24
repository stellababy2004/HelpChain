#!/usr/bin/env python3
"""Check admin 2FA status"""

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
        print("2FA enabled:", admin.two_factor_enabled)
        print("Has TOTP secret:", bool(admin.totp_secret))
    else:
        print("Admin user not found")