#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test AI service configuration
"""

import os
import sys

# Set mock mode for testing
os.environ["AI_DEV_MOCK"] = "1"

# Add backend to path
sys.path.insert(0, "backend")

try:
    from ai_service import ai_service

    print("AI Status:", ai_service.get_ai_status())

    # Test response generation
    result = ai_service.generate_response_sync("Здравей, какво е HelpChain?")
    print("Test response:", result)

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
