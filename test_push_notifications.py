"""
Test script for push notifications
"""

from backend.appy import app
from backend.notification_service import notification_service


def test_push_notifications():
    """Test push notification functionality"""
    with app.app_context():
        print("🧪 Testing push notification system...")

        # Test template retrieval
        template = notification_service.get_template("welcome_push")
        if template:
            print(f"✅ Template found: {template.name}")
            print(f"   Type: {template.type}")
            print(f"   Content: {template.content[:50]}...")
        else:
            print("❌ Template not found")
            return

        # Test template rendering
        test_data = {"name": "Test User"}
        rendered = notification_service.render_template(template, test_data)
        print("✅ Template rendered successfully:")
        print(f"   Title: {rendered.get('title')}")
        print(f"   Content: {rendered.get('content')}")

        print("🎉 Push notification system test completed!")


if __name__ == "__main__":
    test_push_notifications()
