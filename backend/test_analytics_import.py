#!/usr/bin/env python3
"""
Test script to check analytics model imports
"""

try:
    from models_with_analytics import (
        AnalyticsEvent,
        ChatbotConversation,
        PerformanceMetrics,
        UserBehavior,
    )

    print("✅ Analytics models imported successfully")
    print(f"AnalyticsEvent: {AnalyticsEvent}")
    print(f"UserBehavior: {UserBehavior}")
    print(f"PerformanceMetrics: {PerformanceMetrics}")
    print(f"ChatbotConversation: {ChatbotConversation}")
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")
