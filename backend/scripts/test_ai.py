"""scripts/test_ai.py

Helper script to inspect AI provider configuration and run a lightweight connection test.

Usage:
  # from project root (backend):
  python scripts/test_ai.py

It prints environment variables, ai_config provider status, and calls ai_service.test_connection().
"""

import os
import sys

# (keep only stdlib imports at module top)

if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, PROJECT_ROOT)

    # third-party / local imports after sys.path adjustment
    import ai_service
    import ai_config

    print("\nHelpChain AI diagnostic\n" + "=" * 30 + "\n")
    ai_service.print_env()
    # ако ai_config има помощна функция за печат — викаме през модула
    if hasattr(ai_config, "print_ai_config"):
        ai_config.print_ai_config()
    else:
        # fallback: ако ai_service предоставя печат на конфигурацията
        if hasattr(ai_service, "print_ai_config"):
            ai_service.print_ai_config()
    # използваме test_connection от ai_service
    if hasattr(ai_service, "test_connection"):
        ai_service.test_connection()
    print("\nTips:")
    print(" - Уверете се, че AI провайдърите са конфигурирани в .env")
    print(
        " - Example (PowerShell): $env:OPENAI_API_KEY='sk-...' ; python scripts/test_ai.py"
    )
    print(
        " - For persistent config, add keys to the instance config file used by the project (see AI_INTEGRATION_GUIDE.md)."
    )
