"""
Compatibility shim for legacy tests/imports.

Some tests import `appy` directly. We re-export the canonical create_app
from backend.helpchain_backend.src.app so the test suite always uses
the real app factory + registered blueprints.
"""

from backend.helpchain_backend.src.app import create_app  # canonical
from backend.ai_service import ai_service

# Create the Flask app at import time for legacy entrypoints
app = create_app()

__all__ = ["create_app", "ai_service", "app"]
