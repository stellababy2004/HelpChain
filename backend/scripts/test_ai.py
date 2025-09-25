"""scripts/test_ai.py

Helper script to inspect AI provider configuration and run a lightweight connection test.

Usage:
  # from project root (backend):
  python scripts/test_ai.py

It prints environment variables, ai_config provider status, and calls ai_service.test_connection().
"""
import os
import json
import sys

# Add project path to sys.path if needed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai_service import ai_service
from ai_config import ai_config


def print_env():
    keys = [
        'OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_MAX_TOKENS', 'OPENAI_TEMPERATURE',
        'GEMINI_API_KEY', 'GEMINI_MODEL'
    ]
    print("Environment variables (only presence shown):")
    for k in keys:
        v = os.environ.get(k)
        print(f"  {k}: {'SET' if v else 'NOT SET'}")
    print()


def print_ai_config():
    print("ai_config providers:")
    try:
        providers = getattr(ai_config, 'providers', None)
        if not providers:
            print("  No providers found in ai_config")
            return
        for name, p in providers.items():
            enabled = getattr(p, 'enabled', False)
            api_key = getattr(p, 'api_key', None)
            model = getattr(p, 'model', None)
            print(f"  {name}: enabled={enabled}, api_key={'SET' if api_key else 'NOT SET'}, model={model}")
    except Exception as e:
        print("  Error reading ai_config:", e)
    print()


def run_test_connection():
    print("Running ai_service.test_connection()...\n")
    try:
        res = ai_service.test_connection()
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error calling ai_service.test_connection():", e)


if __name__ == '__main__':
    print('\nHelpChain AI diagnostic\n' + '='*30 + '\n')
    print_env()
    print_ai_config()
    run_test_connection()
    print('\nTips:')
    print(' - To enable OpenAI, set OPENAI_API_KEY in your environment or in the project instance config.')
    print(" - Example (PowerShell): $env:OPENAI_API_KEY='sk-...' ; python scripts/test_ai.py")
    print(" - For persistent config, add keys to the instance config file used by the project (see AI_INTEGRATION_GUIDE.md).")
