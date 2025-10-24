#!/usr/bin/env python3
"""
Script to create analytics tables
"""

from appy import app

def main():
    print("🔄 Creating analytics tables...")

    with app.app_context():
        try:
            # Import analytics models to ensure they're registered
            from models_with_analytics import AnalyticsEvent, UserBehavior, PerformanceMetrics, ChatbotConversation

            # Create all tables (this will create analytics tables too)
            from extensions import db
            db.create_all()

            print("✅ Analytics tables created successfully!")

        except Exception as e:
            print(f"❌ Error creating analytics tables: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()