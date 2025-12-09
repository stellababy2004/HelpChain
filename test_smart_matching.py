#!/usr/bin/env python3
"""
Test script for smart matching functionality
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def test_smart_matching():
    """Test the smart matching functionality"""
    try:
        print("Testing smart matching import...")
        from smart_matching import smart_matching_service

        print("✓ Successfully imported smart_matching_service")

        # Initialize Flask app context
        print("\nInitializing Flask app context...")
        from backend.appy import app

        with app.app_context():
            print("✓ App context created")

            print("\nTesting matching analytics...")
            analytics = smart_matching_service.get_matching_analytics()
            print(f"✓ Analytics generated: {len(analytics)} metrics")
            print(f"  - Total requests: {analytics.get('total_requests', 0)}")
            print(f"  - Total volunteers: {analytics.get('total_volunteers', 0)}")

            print("\nTesting AI insights (mock)...")
            # Test AI insights with a mock request ID
            insights = smart_matching_service.get_ai_insights(1)
            print(f"✓ AI insights generated: {insights.get('ai_processed', False)}")

            print("\n🎉 Smart matching system tests passed!")

            # Print sample analytics
            if analytics:
                print("\nSample analytics:")
                print(f"  - Assignment rate: {analytics.get('assignment_rate', 0)}%")
                print(f"  - Completion rate: {analytics.get('completion_rate', 0)}%")
                print(
                    f"  - Average volunteer rating: {analytics.get('avg_volunteer_rating', 0):.1f}"
                )

    except Exception as e:
        print(f"❌ Error testing smart matching: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = test_smart_matching()
    sys.exit(0 if success else 1)
