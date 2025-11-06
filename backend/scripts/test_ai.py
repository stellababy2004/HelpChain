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
    import ai_config
    import ai_service

    print("\nHelpChain AI diagnostic\n" + "=" * 30 + "\n")

    # Ако ai_service има помощна функция — използваме я, иначе fallback
    if hasattr(ai_service, "print_env"):
        ai_service.print_env()
    else:
        # безопасен fallback: отпечатваме релевантни env променливи
        keys = [
            k
            for k in os.environ.keys()
            if any(p in k for p in ("OPENAI", "AZURE", "AI_", "API_KEY"))
        ]
        if not keys:
            print("No AI-related environment variables found.")
        else:
            print("AI-related environment variables:")
            for k in sorted(keys):
                print(
                    f" - {k} = {'<redacted>' if 'KEY' in k or 'SECRET' in k or 'TOKEN' in k else os.environ.get(k)}"
                )
        # кратко резюме от ai_config (ако има методи/атрибути за провайдъри)
        if hasattr(ai_config, "get_providers"):
            try:
                print(
                    "\nai_config.providers:",
                    getattr(ai_config, "providers", "No providers attribute"),
                )
            except Exception:
                print("\nai_config: get_providers() raised an exception")
        elif hasattr(ai_config, "providers"):
            print(
                "\nai_config.providers:",
                getattr(ai_config, "providers", "No providers attribute"),
            )
        else:
            print("\nai_config summary: (no explicit providers attribute)")

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
