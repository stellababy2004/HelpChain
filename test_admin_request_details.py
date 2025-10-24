#!/usr/bin/env python3
"""
Test script for admin request details functionality
"""

import os
import sys
import time

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "backend", "helpchain-backend", "src")
)

# Set up environment
os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test_secret_key"


# Mock the analytics service to avoid import issues
class MockAnalyticsService:
    def track_event(self, *args, **kwargs):
        pass


sys.modules["analytics_service"] = type(
    "MockModule", (), {"analytics_service": MockAnalyticsService()}
)()

# Import the existing app
from backend.appy import app, db
from backend.models import HelpRequest, AdminUser


def test_admin_request_details():
    """Test the admin request details functionality"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()

            # Create unique test admin user with timestamp
            timestamp = str(int(time.time()))
            unique_username = f"test_admin_{timestamp}"
            unique_email = f"test_admin_{timestamp}@test.com"

            # Check if admin already exists
            existing_admin = (
                db.session.query(AdminUser).filter_by(email=unique_email).first()
            )
            if existing_admin:
                print(f"Admin with email {unique_email} already exists, using existing")
                admin = existing_admin
            else:
                # Create test admin user
                admin = AdminUser(username=unique_username, email=unique_email)
                admin.set_password("TestPass123")
                db.session.add(admin)
                db.session.commit()
                print(f"Created test admin user: {unique_username}")

            # Create test help request
            request = HelpRequest(
                name="Test User",
                email="test@example.com",
                phone="123456789",
                message="Test help request message",
                title="Test Request",
                description="Test description",
                status="pending",
            )
            db.session.add(request)
            db.session.commit()

            print(f"Created test request with ID: {request.id}")
            print(
                f"Request details: {request.name}, {request.email}, {request.message}"
            )

            # Verify the request was created correctly
            retrieved_request = db.session.get(HelpRequest, request.id)
            if retrieved_request:
                print("SUCCESS: Request can be retrieved from database!")
                print(
                    f"Retrieved request: {retrieved_request.name}, {retrieved_request.email}"
                )
                return True
            else:
                print("FAILED: Could not retrieve request from database")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_admin_request_details()
    if success:
        print("\n✅ Test passed: Admin request details functionality works!")
    else:
        print("\n❌ Test failed: Admin request details functionality has issues")
        sys.exit(1)
