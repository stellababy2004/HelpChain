#!/usr/bin/env python3
"""
Simple test to check if volunteers table exists and can be queried
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

try:
    from backend.extensions import db
    from backend.appy import app
    from backend.models import Volunteer

    with app.app_context():
        # Try to query volunteers
        count = db.session.query(Volunteer).count()
        print(f"✅ Volunteers table exists. Count: {count}")

        # Try to get first volunteer
        volunteer = db.session.query(Volunteer).first()
        if volunteer:
            print(f"✅ First volunteer: {volunteer.name} ({volunteer.email})")
        else:
            print("ℹ️ No volunteers in database yet")

        print("✅ Database and Volunteer model working correctly!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
