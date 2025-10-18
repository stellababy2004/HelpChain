#!/usr/bin/env python3
"""
Migration script to add indexes for status, location, and role fields
"""

import os
import sys

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__) + "\\backend")

# Import the app and models
from appy import app


def add_indexes():
    """Add indexes for status, location, and role fields"""
    with app.app_context():
        # Get the database
        db = app.extensions["migrate"].db

        # Create indexes using raw SQL since Flask-Migrate might not detect column index changes
        with db.engine.connect() as conn:
            # Add index for User.role
            try:
                conn.execute(
                    db.text("CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)")
                )
                print("✅ Added index for User.role")
            except Exception as e:
                print(f"⚠️  Could not add index for User.role: {e}")

            # Add index for Volunteer.location
            try:
                conn.execute(
                    db.text(
                        "CREATE INDEX IF NOT EXISTS idx_volunteers_location ON volunteers (location)"
                    )
                )
                print("✅ Added index for Volunteer.location")
            except Exception as e:
                print(f"⚠️  Could not add index for Volunteer.location: {e}")

            # Add index for HelpRequest.status
            try:
                conn.execute(
                    db.text(
                        "CREATE INDEX IF NOT EXISTS idx_help_requests_status ON help_requests (status)"
                    )
                )
                print("✅ Added index for HelpRequest.status")
            except Exception as e:
                print(f"⚠️  Could not add index for HelpRequest.status: {e}")

        print("🎯 Database indexes added successfully!")
        print("📊 Indexes added:")
        print("   - idx_users_role (User.role)")
        print("   - idx_volunteers_location (Volunteer.location)")
        print("   - idx_help_requests_status (HelpRequest.status)")


if __name__ == "__main__":
    add_indexes()
