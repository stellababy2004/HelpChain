#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for AI functionality
"""

import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.ai_service import ai_service

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
