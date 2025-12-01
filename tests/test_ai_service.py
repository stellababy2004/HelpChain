#!/usr/bin/env python3
"""
Test AI service configuration
"""

import os

# Set mock mode for testing
os.environ["AI_DEV_MOCK"] = "1"

try:
    from backend.ai_service import ai_service

    print("AI Status:", ai_service.get_ai_status())

    # Test response generation
    result = ai_service.generate_response_sync("Здравей, какво е HelpChain?")
    print("Test response:", result)

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
