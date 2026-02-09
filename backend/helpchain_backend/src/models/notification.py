"""
Compatibility wrapper for the canonical Notification model.

We keep this module name to satisfy imports like
`from backend.helpchain_backend.src.models.notification import Notification`,
but we must not define a second SQLAlchemy table mapping here.
"""

from backend.models import Notification  # noqa: F401
