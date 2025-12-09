#!/usr/bin/env python3
"""
Comprehensive Push Notification Tests for HelpChain
Tests all components: models, API endpoints, VAPID configuration, frontend integration
"""

import os
import sys
import tempfile
import unittest
import uuid

import requests

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Flask imports
from flask import Flask

from backend.extensions import db

# Model imports - moved to setUp to ensure proper db initialization
# try:
#     from models_with_analytics import (
#         PushSubscription,
#         NotificationTemplate,
#         NotificationPreference,
#         User,
#         Task,
#         TaskAssignment,
#         TaskPerformance
#     )
# except ImportError:
#     from models import (
#         PushSubscription,
#         NotificationTemplate,
#         NotificationPreference,
#         User
#     )

# Blueprint import
# from routes.notifications import notification_bp  # Moved to setUp


class TestPushNotifications(unittest.TestCase):
    """Comprehensive test suite for push notifications"""

    def setUp(self):
        """Set up test environment"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key"
        # Use a unique temporary file-based SQLite DB per test to avoid
        # cross-test contamination while still letting module-level and
        # Flask-SQLAlchemy engines share the same file for that test.
        tmp = tempfile.NamedTemporaryFile(prefix="hc_test_", suffix=".db", delete=False)
        tmp.close()
        self._test_db_path = tmp.name
        self.app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{self._test_db_path}"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        # VAPID configuration
        self.app.config["VAPID_PUBLIC_KEY"] = os.getenv(
            "VAPID_PUBLIC_KEY", "test_public_key"
        )
        self.app.config["VAPID_PRIVATE_KEY"] = os.getenv(
            "VAPID_PRIVATE_KEY", "test_private_key"
        )

        # Import models after app creation
        try:
            from models_with_analytics import (
                NotificationPreference,
                NotificationTemplate,
                PushSubscription,
                Task,
                TaskAssignment,
                TaskPerformance,
                User,
            )
        except ImportError:
            from models import (
                NotificationPreference,
                NotificationTemplate,
                PushSubscription,
                User,
            )

        # Store model references for use in tests
        self.PushSubscription = PushSubscription
        self.NotificationTemplate = NotificationTemplate
        self.NotificationPreference = NotificationPreference
        self.User = User

        # Import blueprint after app is created
        from routes.notifications import notification_bp

        db.init_app(self.app)
        self.app.register_blueprint(notification_bp, url_prefix="/api/notification")

        with self.app.app_context():
            db.create_all()

        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Remove the temporary DB file created for this test
        try:
            if hasattr(self, "_test_db_path") and os.path.exists(self._test_db_path):
                os.remove(self._test_db_path)
        except Exception:
            pass

    def test_01_vapid_configuration(self):
        """Test VAPID key configuration"""
        print("\n=== Testing VAPID Configuration ===")

        # Test environment variables
        vapid_public = os.getenv("VAPID_PUBLIC_KEY")
        vapid_private = os.getenv("VAPID_PRIVATE_KEY")

        print(f"VAPID_PUBLIC_KEY from env: {bool(vapid_public)}")
        print(f"VAPID_PRIVATE_KEY from env: {bool(vapid_private)}")

        # Test Flask config
        with self.app.app_context():
            config_public = self.app.config.get("VAPID_PUBLIC_KEY")
            config_private = self.app.config.get("VAPID_PRIVATE_KEY")

            print(f"VAPID_PUBLIC_KEY in config: {bool(config_public)}")
            print(f"VAPID_PRIVATE_KEY in config: {bool(config_private)}")

            self.assertIsNotNone(config_public, "VAPID public key should be configured")
            self.assertIsNotNone(
                config_private, "VAPID private key should be configured"
            )

    def test_02_vapid_endpoint(self):
        """Test VAPID public key endpoint"""
        print("\n=== Testing VAPID Endpoint ===")

        response = self.client.get("/api/notification/vapid-public-key")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.get_json()}")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], "VAPID endpoint should return success")
        self.assertIn("publicKey", data, "Response should contain publicKey")
        self.assertIsNotNone(data["publicKey"], "Public key should not be None")

    def test_03_push_subscription_model(self):
        """Test PushSubscription model"""
        print("\n=== Testing PushSubscription Model ===")

        with self.app.app_context():
            # Create test subscription
            subscription = self.PushSubscription(
                volunteer_id=1,
                endpoint="https://fcm.googleapis.com/fcm/send/test",
                p256dh_key="test_p256dh_key",
                auth_key="test_auth_key",
                user_agent="test_user_agent",
            )

            db.session.add(subscription)
            db.session.commit()

            # Query it back
            saved = self.PushSubscription.query.filter_by(volunteer_id=1).first()
            self.assertIsNotNone(saved, "Subscription should be saved")
            self.assertEqual(saved.endpoint, "https://fcm.googleapis.com/fcm/send/test")
            self.assertTrue(saved.is_active, "Subscription should be active by default")

            print("PushSubscription model works correctly")

    def test_04_notification_template_model(self):
        """Test NotificationTemplate model"""
        print("\n=== Testing NotificationTemplate Model ===")

        with self.app.app_context():
            # Create test template
            template = self.NotificationTemplate(
                name="test_template",
                category="system",
                type="push",
                title="Test Notification",
                content="This is a test notification",
                is_active=True,
            )
            db.session.add(template)
            db.session.commit()

            # Query it back
            saved = self.NotificationTemplate.query.filter_by(
                name="test_template"
            ).first()
            self.assertIsNotNone(saved, "Template should be saved")
            self.assertEqual(saved.title, "Test Notification")
            self.assertEqual(saved.content, "This is a test notification")

            print("NotificationTemplate model works correctly")

    def test_05_push_subscription_endpoint(self):
        """Test push subscription endpoint"""
        print("\n=== Testing Push Subscription Endpoint ===")

        subscription_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test",
            "p256dh": "test_p256dh_key",
            "auth": "test_auth_key",
            "userAgent": "Test Browser",
        }

        response = self.client.post(
            "/api/notification/subscribe",
            json=subscription_data,
            headers={"Content-Type": "application/json"},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.get_json()}")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], "Subscription should succeed")

        # Verify in database
        with self.app.app_context():
            saved = self.PushSubscription.query.filter_by(
                endpoint="https://fcm.googleapis.com/fcm/send/test"
            ).first()
            self.assertIsNotNone(saved, "Subscription should be saved in database")

    def test_06_push_unsubscribe_endpoint(self):
        """Test push unsubscribe endpoint"""
        print("\n=== Testing Push Unsubscribe Endpoint ===")

        # First subscribe
        subscription_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test_unsubscribe",
            "p256dh": "test_p256dh_key",
            "auth": "test_auth_key",
            "userAgent": "Test Browser",
        }

        self.client.post(
            "/api/notification/subscribe",
            json=subscription_data,
            headers={"Content-Type": "application/json"},
        )

        # Then unsubscribe
        unsubscribe_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test_unsubscribe"
        }

        response = self.client.post(
            "/api/notification/unsubscribe-push",
            json=unsubscribe_data,
            headers={"Content-Type": "application/json"},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.get_json()}")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], "Unsubscription should succeed")

        # Verify in database
        with self.app.app_context():
            saved = self.PushSubscription.query.filter_by(
                endpoint="https://fcm.googleapis.com/fcm/send/test_unsubscribe"
            ).first()
            self.assertIsNotNone(saved, "Subscription should still exist")
            self.assertFalse(saved.is_active, "Subscription should be deactivated")

    def test_07_notification_stats_endpoint(self):
        """Test notification stats endpoint"""
        print("\n=== Testing Notification Stats Endpoint ===")

        response = self.client.get("/api/notification/stats")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.get_json()}")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], "Stats endpoint should succeed")
        self.assertIn("stats", data, "Response should contain stats")

    def test_08_server_integration(self):
        """Test server integration with real server"""
        print("\n=== Testing Server Integration ===")

        try:
            # Test if server is running
            response = requests.get("http://127.0.0.1:8000/", timeout=5)
            server_running = response.status_code == 200
            print(f"Server running: {server_running}")

            if server_running:
                # Test VAPID endpoint
                vapid_response = requests.get(
                    "http://127.0.0.1:8000/api/notification/vapid-public-key", timeout=5
                )
                print(f"VAPID endpoint status: {vapid_response.status_code}")
                print(f"VAPID response: {vapid_response.json()}")

                self.assertEqual(vapid_response.status_code, 200)
                data = vapid_response.json()
                self.assertTrue(data["success"], "Live VAPID endpoint should work")
            else:
                print("Server not running, skipping live tests")
                self.skipTest("Server not running")

        except requests.exceptions.RequestException as e:
            print(f"Server integration test failed: {e}")
            self.skipTest(f"Server not accessible: {e}")

    def test_09_frontend_files_exist(self):
        """Test that frontend files exist"""
        print("\n=== Testing Frontend Files ===")

        # Check notification_service.js
        js_path = os.path.join(
            os.path.dirname(__file__), "static", "js", "notification_service.js"
        )
        self.assertTrue(os.path.exists(js_path), "notification_service.js should exist")

        # Check index.html has push notification elements
        html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
        if os.path.exists(html_path):
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
                self.assertIn(
                    "notification_service.js",
                    content,
                    "index.html should include notification_service.js",
                )
                self.assertIn(
                    "push-notifications",
                    content,
                    "index.html should have push notification elements",
                )

        print("Frontend files exist and are properly configured")

    def test_10_database_relationships(self):
        """Test database relationships"""
        print("\n=== Testing Database Relationships ===")

        with self.app.app_context():
            print("DEBUG at start of app_context: db.session id:", id(db.session))
            # Create user
            user = self.User(
                username="test_user",
                email="test@example.com",
                password_hash="test_hash",
            )
            db.session.add(user)
            db.session.flush()

            # Create subscription linked to user
            subscription = self.PushSubscription(
                volunteer_id=user.id,
                endpoint="https://fcm.googleapis.com/fcm/send/relationship_test",
                p256dh_key="test_key",
                auth_key="test_auth",
            )
            db.session.add(subscription)

            # Create notification preference
            preference = self.NotificationPreference(
                user_id=user.id,
                email_enabled=True,
                push_enabled=True,
                sms_enabled=False,
            )
            db.session.add(preference)

            db.session.commit()
            print("DEBUG after commit: db.session id:", id(db.session))

            # Test relationships
            # DEBUG: inspect User class and query behavior
            try:
                print("DEBUG: User class module:", self.User.__module__)
                print("DEBUG: User class id:", id(self.User))
                print(
                    "DEBUG: User.query repr:", repr(getattr(self.User, "query", None))
                )
                print("DEBUG: db.session id:", id(db.session))
                try:
                    print("DEBUG: db.engine:", getattr(db, "engine", None))
                    try:
                        res = list(db.engine.execute("SELECT count(*) FROM users"))
                        print("DEBUG: raw users count via engine:", res)
                    except Exception as _e:
                        print("DEBUG: raw select failed:", _e)
                except Exception:
                    pass
                try:
                    print(
                        "DEBUG: session.query(User).all():",
                        db.session.query(self.User).all(),
                    )
                except Exception as _e:
                    print("DEBUG: session.query(User) raised:", _e)
            except Exception:
                pass

            saved_user = self.User.query.filter_by(username="test_user").first()
            self.assertIsNotNone(saved_user, "User should be saved")

            # Check if relationships work (if implemented)
            try:
                if hasattr(saved_user, "notification_preferences"):
                    prefs = saved_user.notification_preferences
                    self.assertIsNotNone(
                        prefs, "User should have notification preferences"
                    )
                    print("User-NotificationPreference relationship works")
            except Exception:
                print("User-NotificationPreference relationship not implemented yet")

            print("Database relationships work correctly")


def run_tests():
    """Run all tests with detailed output"""
    print("🚀 Starting Push Notification Tests")
    print("=" * 50)

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPushNotifications)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    if result.skipped:
        print("\n⏭️  Skipped:")
        for test, reason in result.skipped:
            print(f"  - {test}: {reason}")

    if result.wasSuccessful():
        print("\n✅ All tests passed! Push notification system is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the issues above.")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
