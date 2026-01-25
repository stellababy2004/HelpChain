"""
Compatibility wrapper.

Do NOT create extension instances here.
Re-export the canonical ones from backend.helpchain_backend.src.extensions.
"""

from backend.helpchain_backend.src.extensions import babel, mail
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

__all__ = ["db", "mail", "babel", "migrate"]
