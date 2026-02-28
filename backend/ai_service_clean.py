"""
Legacy compatibility shim.

Older modules/tests import:
    from backend.ai_service_clean import ai_service

The canonical implementation lives in:
    backend.ai_service (ai_service = AIService()).
"""

from backend.ai_service import ai_service

