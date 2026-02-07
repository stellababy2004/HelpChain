"""
Canonical models package for HelpChain backend.

All models should be imported here exactly once to keep a single SQLAlchemy
MetaData registry. Legacy models defined in `backend.models` are re-exported
so existing imports keep working, but they use the SAME `db` instance from
backend.extensions.
"""

from backend.extensions import db

# Re-export legacy monolith models (single metadata)
from backend import models as _legacy_models  # noqa: E402

# Explicitly import modern split models
from .volunteer_interest import VolunteerInterest  # noqa: E402,F401
from .refresh_token import RefreshToken  # noqa: E402,F401
from .volunteer_action import VolunteerAction  # noqa: E402,F401


# Collect public names from legacy + modern models
_public = set()
for name in (
    "AdminUser",
    "Request",
    "RequestLog",
    "RequestActivity",
    "RequestMetric",
    "User",
    "Volunteer",
    "PushSubscription",
    "Feedback",
    "NotificationSubscription",
    "Notification",
    "canonical_role",
    "utc_now",
):
    if hasattr(_legacy_models, name):
        globals()[name] = getattr(_legacy_models, name)
        _public.add(name)

globals()["VolunteerInterest"] = VolunteerInterest
_public.add("VolunteerInterest")
globals()["RefreshToken"] = RefreshToken
_public.add("RefreshToken")
globals()["VolunteerAction"] = VolunteerAction
_public.add("VolunteerAction")

__all__ = ["db", *sorted(_public)]

