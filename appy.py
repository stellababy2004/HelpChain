"""
Compatibility shim for legacy tests/imports.

Some tests import `appy` directly. We re-export the canonical create_app
from backend.helpchain_backend.src.app so the test suite always uses
the real app factory + registered blueprints.
"""

from backend.ai_service import ai_service
from backend.helpchain_backend.src.app import create_app  # canonical

__all__ = ["create_app", "ai_service"]
