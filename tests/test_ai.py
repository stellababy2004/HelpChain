#!/usr/bin/env python3
"""
Test script for AI functionality
"""

import os
import sys

from dotenv import load_dotenv

from backend.ai_service_clean import ai_service

load_dotenv()


def test_ai():
    """Test AI responses"""
    print("🤖 Testing HelpChain AI Service")
    print("=" * 50)

    test_questions = [
        "Здравей",
        "Какво е HelpChain?",
        "Как да се регистрирам?",
        "Колко струва?",
        "Как да стана доброволец?",
        "Къде работите?",
        "Какви услуги предлагате?",
        "Имам нужда от помощ с пазаруване",
    ]

    for question in test_questions:
        print(f"\n❓ {question}")
        try:
            result = ai_service.generate_response_sync(question)
            print(f"🤖 {result['response']}")
            print(
                f"📊 Confidence: {result['confidence']}, Provider: {result['provider']}"
            )
        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n" + "=" * 50)
    print("✅ AI testing completed!")


if __name__ == "__main__":
    test_ai()
