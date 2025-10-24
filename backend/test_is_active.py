#!/usr/bin/env python3
"""
Test script to verify the is_active field works in Volunteer model
"""
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from appy import app  # Import the Flask app directly
from models import Volunteer, db


def test_is_active_field():
    """Test that the is_active field works correctly"""
    with app.app_context():
        try:
            # Test querying volunteers with is_active=True
            active_volunteers = (
                db.session.query(Volunteer).filter_by(is_active=True).all()
            )
            print(f"Found {len(active_volunteers)} active volunteers")

            # Test querying volunteers with is_active=False
            inactive_volunteers = (
                db.session.query(Volunteer).filter_by(is_active=False).all()
            )
            print(f"Found {len(inactive_volunteers)} inactive volunteers")

            # Test that we can create a volunteer with is_active field
            test_volunteer = Volunteer(
                name="Test Volunteer",
                email="test@example.com",
                phone="123456789",
                location="Test City",
                is_active=True,
            )
            db.session.add(test_volunteer)
            db.session.commit()
            print(f"Created test volunteer with ID: {test_volunteer.id}")

            # Clean up
            db.session.delete(test_volunteer)
            db.session.commit()
            print("Cleaned up test volunteer")

            return True

        except Exception as e:
            print(f"Error testing is_active field: {e}")
            db.session.rollback()
            return False


if __name__ == "__main__":
    success = test_is_active_field()
    if success:
        print("is_active field test completed successfully!")
    else:
        print("is_active field test failed!")
        sys.exit(1)
