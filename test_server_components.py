#!/usr/bin/env python3
"""
Quick test suite for HelpChain Flask server components
Tests imports, blueprint registration, and basic functionality without starting HTTP server
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))


def test_imports():
    """Test that all critical modules can be imported"""
    print("Testing imports...")

    try:
        # Test core Flask app
        from appy import create_app

        print("✓ Flask app creation function imported")

        # Test admin blueprint
        from admin_bp import admin_bp

        print("✓ Admin blueprint imported")

        # Test models
        from models import AdminUser, HelpRequest, Volunteer

        print("✓ Core models imported")

        # Test extensions
        from backend.extensions import db, mail

        print("✓ Database and mail extensions imported")

        # Test analytics service
        try:
            from analytics_service import analytics_service

            print("✓ Analytics service imported")
        except ImportError as e:
            print(f"⚠ Analytics service import failed (optional): {e}")

        # Test AI service
        try:
            from ai_service import ai_service

            print("✓ AI service imported")
        except ImportError as e:
            print(f"⚠ AI service import failed (optional): {e}")

        return True

    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_blueprint_registration():
    """Test that blueprints can be registered without errors"""
    print("\nTesting blueprint registration...")

    try:
        from appy import create_app

        # Create app in test mode
        app = create_app(config_object="config.TestingConfig")

        with app.app_context():
            # Check that admin blueprint is registered
            admin_registered = "admin" in app.blueprints
            print(
                f"{'✓' if admin_registered else '✗'} Admin blueprint registered: {admin_registered}"
            )

            # Check that other blueprints are registered
            blueprints_to_check = ["analytics_main", "notification"]
            for bp_name in blueprints_to_check:
                registered = bp_name in app.blueprints
                print(
                    f"{'✓' if registered else '⚠'} {bp_name} blueprint registered: {registered}"
                )

            return admin_registered

    except Exception as e:
        print(f"✗ Blueprint registration failed: {e}")
        return False


def test_database_initialization():
    """Test database initialization"""
    print("\nTesting database initialization...")

    try:
        from appy import create_app

        app = create_app(config_object="config.TestingConfig")

        with app.app_context():
            # Try to create all tables
            from backend.extensions import db

            db.create_all()
            print("✓ Database tables created")

            # Check if admin user exists
            from models import AdminUser

            admin_count = AdminUser.query.count()
            print(f"✓ Admin users in database: {admin_count}")

            return True

    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False


def test_admin_authentication_logic():
    """Test admin authentication logic without HTTP"""
    print("\nTesting admin authentication logic...")

    try:
        from appy import create_app
        from models import AdminUser

        app = create_app(config_object="config.TestingConfig")

        with app.app_context():
            # Get or create default admin
            from appy import initialize_default_admin

            admin_user = initialize_default_admin()

            if admin_user:
                print("✓ Default admin user initialized")

                # Test password checking
                valid_password = admin_user.check_password("test-password")
                print(f"✓ Default password check: {valid_password}")

                return valid_password
            else:
                print("✗ Failed to initialize default admin")
                return False

    except Exception as e:
        print(f"✗ Admin authentication test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("HelpChain Server Component Test Suite")
    print("=" * 60)

    tests = [
        test_imports,
        test_blueprint_registration,
        test_database_initialization,
        test_admin_authentication_logic,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success rate: {passed / total * 100:.1f}%" if total > 0 else "No tests run")

    if passed == total:
        print("\n🎉 ALL COMPONENT TESTS PASSED!")
        print("The HelpChain server components are properly configured.")
        return True
    else:
        print("\n❌ Some component tests failed.")
        print("Check the server configuration and dependencies.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

