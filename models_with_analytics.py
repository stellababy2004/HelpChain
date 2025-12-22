# Compatibility shim to expose `backend.models_with_analytics` at the top level
# so imports like `from models_with_analytics import AnalyticsEvent, Feedback`
# work when running scripts or tests from the repository root.

try:
    from backend.models_with_analytics import *  # type: ignore
except Exception:
    # Minimal fallback to avoid hard import failure during early collection.
    pass
