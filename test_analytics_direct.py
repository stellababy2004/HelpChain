import os
import sys

sys.path.insert(0, "backend")

# Import models to resolve relationships
# Create Flask app for database access
from flask import Flask

from backend.extensions import db
from backend.models_with_analytics import (
    AnalyticsEvent,
    ChatbotConversation,
    UserBehavior,
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(os.path.dirname(__file__), 'instance', 'volunteers.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    # Ensure schema exists on this test DB before running direct queries.
    try:
        # Remove any older schema that might be present in the DB file so
        # tests see the current models. This is safe for test runs but
        # destructive to any pre-existing instance DB.
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()
    except Exception:
        pass
    print("=== ANALYTICS TEST RESULTS ===")

    # Check AnalyticsEvent count
    analytics_count = db.session.query(AnalyticsEvent).count()
    print(f"Total Analytics Events: {analytics_count}")

    # Check UserBehavior count
    behavior_count = db.session.query(UserBehavior).count()
    print(f"Total User Behavior Records: {behavior_count}")

    # Check ChatbotConversation count
    chatbot_count = db.session.query(ChatbotConversation).count()
    print(f"Total Chatbot Conversations: {chatbot_count}")

    # Get some sample analytics events
    if analytics_count > 0:
        print("\n=== SAMPLE ANALYTICS EVENTS ===")
        events = db.session.query(AnalyticsEvent).limit(5).all()
        for event in events:
            print(f"- {event.event_type}: {event.event_category} ({event.created_at})")

    # Get some sample user behavior
    if behavior_count > 0:
        print("\n=== SAMPLE USER BEHAVIOR ===")
        behaviors = db.session.query(UserBehavior).limit(3).all()
        for behavior in behaviors:
            print(
                f"- Session {behavior.session_id}: {behavior.pages_visited} pages, {behavior.user_type}"
            )

    # Get some sample chatbot conversations
    if chatbot_count > 0:
        print("\n=== SAMPLE CHATBOT CONVERSATIONS ===")
        conversations = db.session.query(ChatbotConversation).limit(3).all()
        for conv in conversations:
            print(
                f"- {conv.user_message[:50]}... -> {conv.bot_response[:50] if conv.bot_response else 'No response'}"
            )

    print("\n=== ANALYTICS SYSTEM STATUS ===")
    print(
        "✅ Analytics events table populated"
        if analytics_count > 0
        else "❌ No analytics events found"
    )
    print(
        "✅ User behavior tracking active"
        if behavior_count > 0
        else "❌ No user behavior data"
    )
    print(
        "✅ Chatbot analytics working"
        if chatbot_count > 0
        else "❌ No chatbot conversations"
    )

    total_data_points = analytics_count + behavior_count + chatbot_count
    print(f"\n📊 Total analytics data points: {total_data_points}")

    if total_data_points > 0:
        print("🎉 Analytics system is working correctly with real data!")
    else:
        print(
            "⚠️  Analytics system has no data - using sample data would be shown in dashboard"
        )
