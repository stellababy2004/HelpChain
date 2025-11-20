from flask_babel import Babel
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

# Optional imports - handle gracefully if not available
try:
    from flask_caching import Cache

    FLASK_CACHING_AVAILABLE = True
except ImportError:
    FLASK_CACHING_AVAILABLE = False
    Cache = None

# Reuse any existing top-level `extensions` module's objects if present.
# This guards against the same file being loaded under both the package
# name (`backend.extensions`) and the top-level name (`extensions`) which
# would otherwise create two distinct SQLAlchemy() instances.
import os
import sys

_existing = sys.modules.get("extensions")
if _existing is not None:
    try:
        _existing_db = getattr(_existing, "db", None)
    except Exception:
        _existing_db = None
else:
    _existing_db = None

if _existing_db is not None:
    # Reuse the existing SQLAlchemy instance from the top-level module
    db = _existing_db
else:
    db = SQLAlchemy()

try:
    _existing_babel = (
        getattr(_existing, "babel", None) if _existing is not None else None
    )
except Exception:
    _existing_babel = None
babel = _existing_babel if _existing_babel is not None else Babel()

try:
    _existing_mail = getattr(_existing, "mail", None) if _existing is not None else None
except Exception:
    _existing_mail = None
mail = _existing_mail if _existing_mail is not None else Mail()

# If a duplicate top-level `extensions` module object exists and it exposes
# a different SQLAlchemy instance, attempt to migrate any Table objects
# into the canonical metadata so mapped classes become visible to the
# single app-provided `db` instance. Then ensure the short-name maps to
# this canonical module object.
try:
    dup_mod = sys.modules.get("extensions")
    if dup_mod is not None and dup_mod is not sys.modules.get(__name__):
        try:
            dup_db = getattr(dup_mod, "db", None)
        except Exception:
            dup_db = None
        try:
            if dup_db is not None and id(dup_db) != id(db):
                # Move any tables from the duplicate metadata into canonical
                for tbl in list(
                    getattr(getattr(dup_db, "metadata", {}), "tables", {}).values()
                ):
                    try:
                        if (
                            getattr(tbl, "name", None)
                            not in getattr(db, "metadata", {}).tables
                        ):
                            tbl.tometadata(db.metadata)
                    except Exception as _e:
                        # Provide debug output when requested to help CI diagnostics
                        if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                            try:
                                import traceback as _tb

                                print(
                                    "[EXT DEBUG] failed to move table into canonical metadata:",
                                    getattr(tbl, "name", None),
                                )
                                print(_tb.format_exc())
                            except Exception:
                                pass
                        # otherwise ignore silently
                        pass
        except Exception:
            pass
        # Ensure future imports under the short name return this module
        try:
            sys.modules["extensions"] = sys.modules.get(__name__)
        except Exception:
            pass
except Exception:
    pass

# Initialize cache conditionally
if FLASK_CACHING_AVAILABLE:
    cache = Cache()
else:
    cache = None

import extensions
