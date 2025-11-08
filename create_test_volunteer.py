#!/usr/bin/env python3
"""
Create a test volunteer account for testing purposes.
This account bypasses email verification for easier testing.
"""

import os
import sys
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

try:
    from appy import app, db
    from models import Volunteer

    def create_test_volunteer():
        """Create a test volunteer account"""
        with app.app_context():
            # Check if test volunteer already exists
            existing = (
                db.session.query(Volunteer).filter_by(email="test@example.com").first()
            )
            if existing:
                print(
                    f"Test volunteer already exists: {existing.name} (ID: {existing.id})"
                )
                return existing

            # Create new test volunteer
            test_volunteer = Volunteer(
                name="Test Volunteer",
                email="test@example.com",
                phone="+359 88 123 4567",
                location="София",
                skills="testing, development",
                points=100,
                level=2,
                experience=150,
                created_at=datetime.utcnow(),
            )

            db.session.add(test_volunteer)
            db.session.commit()

            print(
                f"Created test volunteer: {test_volunteer.name} (ID: {test_volunteer.id})"
            )
            print(f"Email: {test_volunteer.email}")
            print("This account bypasses email verification for testing.")

            return test_volunteer

    if __name__ == "__main__":
        try:
            volunteer = create_test_volunteer()
            print("\nTest volunteer account created successfully!")
            print("You can now login with:")
            print("Email: test@example.com")
            print("No password/code required - direct login bypass")
        except Exception as e:
            print(f"Error creating test volunteer: {e}")
            sys.exit(1)

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)
