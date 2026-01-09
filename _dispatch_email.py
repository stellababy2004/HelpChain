# Compatibility shim for legacy imports on Render and tests
# Re-export the backend implementation so `from _dispatch_email import _dispatch_email`
# works regardless of PYTHONPATH
from backend._dispatch_email import _dispatch_email

__all__ = ["_dispatch_email"]
