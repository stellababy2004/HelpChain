"""
Shim module for backward compatibility.

This file previously contained model class definitions which duplicated the
canonical ORM models defined in the top-level `models.py`. To avoid
multiple-registration errors with SQLAlchemy's declarative registry we
export the canonical classes here so other modules that import
`helpchain_backend.src.models` continue to work.

Do not add new model definitions here; update the canonical `models.py`.
"""

# Import and re-export canonical models from top-level models module
from models import (
    AdminUser,
    Feedback,
    RequestLog,
    Volunteer,
)

__all__ = ["RequestLog", "Volunteer", "Feedback", "AdminUser"]
