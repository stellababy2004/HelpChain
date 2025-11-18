# ruff: noqa
from __future__ import annotations
import os
import sys
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

try:
    from backend.models import _load_common_passwords, validate_password_strength
except ModuleNotFoundError:
    try:
        from models import _load_common_passwords, validate_password_strength
    except ModuleNotFoundError:
        raise
"""Smoke test for common password blacklist integration."""

COMMON = [
    "password",
    "123456",
    "qwerty",
    "football",
    "letmein",
    "Password123",
    "qwertyuiop",
]

STRONG = "UncommonStr0ngX123"  # Should pass (length, upper, lower, digits, not common)


def test_blacklist():
    print("[SMOKE] Starting password blacklist test...")
    # Debug membership for Password123
    print(
        "[DEBUG] password123 in blacklist?", "password123" in _load_common_passwords()
    )
    for pwd in COMMON:
        try:
            validate_password_strength(pwd)
            print(f"[FAIL] Common password NOT rejected: {pwd}")
        except ValueError as e:
            # Expect ValueError with common password message
            print(f"[OK] Rejected common password '{pwd}': {e}")

    try:
        validate_password_strength(STRONG)
        print(f"[OK] Strong password accepted: {STRONG}")
    except ValueError as e:
        print(f"[FAIL] Strong password unexpectedly rejected: {e}")


if __name__ == "__main__":
    test_blacklist()
