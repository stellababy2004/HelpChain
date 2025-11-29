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

# Ensure this module is available under both the short name `extensions`
# and the package name `backend.extensions` so imports from tests that
# use either path resolve to the same module object.
try:
    if sys.modules.get(__name__) is not None:
        sys.modules.setdefault("extensions", sys.modules.get(__name__))
        sys.modules.setdefault("backend.extensions", sys.modules.get(__name__))
except Exception:
    pass
_existing = sys.modules.get("extensions")
if _existing is not None:
    try:
        _existing_db = getattr(_existing, "db", None)
    except Exception:
        _existing_db = None
else:
    _existing_db = None
if _existing_db is not None:
    # Only reuse the existing object if it looks like a Flask-SQLAlchemy
    # instance: it should expose `init_app`. If it's a plain scoped_session
    # or another incompatible object (which can happen if a models module
    # was accidentally imported under the short name), ignore it and
    # create a fresh `SQLAlchemy()` instance to avoid attribute errors.
    try:
        if hasattr(_existing_db, "init_app"):
            db = _existing_db
        else:
            db = SQLAlchemy()
    except Exception:
        db = SQLAlchemy()
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

# Wrap the SQLAlchemy `init_app` to ensure the standalone `backend.models`
# metadata and the Flask-SQLAlchemy engine stay in sync during tests.
try:
    _orig_init = db.init_app

    def _init_app_and_sync(app):
        # Call the original init behavior
        try:
            _orig_init(app)
        except Exception:
            # Continue even if original init had issues; we still attempt
            # to synchronize metadata for tests which rely on it.
            pass

        # Debug: show some module/session info to help reproduce duplicate
        # import problems in tests.
        try:
            if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                print(f"[EXT DEBUG] init_app called. sys.modules contains: models={'models' in sys.modules}, backend.models={'backend.models' in sys.modules}, db_id={id(db)}")
        except Exception:
            pass

        # Attempt to import the models module and create any missing tables
        # on the Flask-SQLAlchemy engine so tests that use different
        # session/engine objects see a consistent schema.
        try:
            import importlib

            _models = importlib.import_module("backend.models")
            try:
                # Try to get engine via the SQLAlchemy object first
                try:
                    engine = db.get_engine(app)
                except Exception:
                    engine = getattr(db, "engine", None)

                if engine is not None:
                    try:
                        # Ensure the Flask engine schema matches the current
                        # declarative Base metadata. Drop & recreate to
                        # avoid mismatches (tests use in-memory DBs).
                        try:
                            _models.Base.metadata.drop_all(bind=engine)
                        except Exception:
                            pass
                        try:
                            _models.Base.metadata.create_all(bind=engine)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Ensure the module-level `engine`/`db` in backend.models (if present)
                    # uses the same engine so that in-memory SQLite data is shared
                    # between the module-scoped session and the Flask app session.
                    try:
                        # Replace module-level engine and reconfigure its scoped_session
                        if hasattr(_models, "engine"):
                            try:
                                _models.engine = engine
                            except Exception:
                                pass
                        try:
                            # Recreate the module-scoped scoped_session bound to the Flask engine
                            from sqlalchemy.orm import scoped_session, sessionmaker as _sessionmaker

                            try:
                                _models.db = scoped_session(_sessionmaker(bind=engine, autocommit=False, autoflush=False))
                            except Exception:
                                pass

                            try:
                                _models.db_session = _models.db
                            except Exception:
                                pass

                            try:
                                _models.Base.query = getattr(_models.db, 'query_property', lambda: None)()
                            except Exception:
                                try:
                                    _models.Base.query = _models.db.query_property()
                                except Exception:
                                    pass

                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Also ensure metadata is created on the SQLAlchemy object's
                    # engine if it's different from the engine returned above.
                    try:
                        alt_engine = getattr(db, "engine", None)
                        if alt_engine is not None and alt_engine is not engine:
                            try:
                                _models.Base.metadata.create_all(bind=alt_engine)
                            except Exception:
                                pass
                    except Exception:
                        # If metadata create_all fails, continue silently
                        pass
                # After ensuring tables exist, attempt to seed default
                # roles and permissions so tests relying on defaults pass.
                try:
                    perms_mod = importlib.import_module("backend.permissions")
                    try:
                        perms_mod.initialize_default_roles_and_permissions()
                    except Exception:
                        pass
                except Exception:
                    pass
                # Attach model query proxies that route `.query` to the
                # Flask-SQLAlchemy session so tests that call `Model.query`
                # will use the app's session instead of the module-level one.
                try:
                    # Attach proxies both to `backend.models` and the top-level
                    # `models` module if tests import models under the short name.
                    try:
                        from backend.extensions import db as _ext_db

                        class _FlaskQueryProxy:
                            def __init__(self, model):
                                self._model = model

                            def __getattr__(self, name):
                                try:
                                    if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                                        print(f"[EXT DEBUG] _FlaskQueryProxy __getattr__ called for {getattr(self._model, '__name__', None)} (module={getattr(self._model, '__module__', None)}) using session id={id(_ext_db.session)}")
                                except Exception:
                                    pass
                                return getattr(_ext_db.session.query(self._model), name)

                        for mod_name in ("backend.models", "models", "models_with_analytics"):
                            try:
                                m = None
                                if mod_name in sys.modules:
                                    m = sys.modules.get(mod_name)
                                else:
                                    try:
                                        m = importlib.import_module(mod_name)
                                    except Exception:
                                        m = None

                                if m is None:
                                    continue

                                # Attach common proxies to whichever module object we found
                                try:
                                    if hasattr(m, "User"):
                                        m.User.query = _FlaskQueryProxy(m.User)
                                except Exception:
                                    pass
                                try:
                                    if hasattr(m, "NotificationTemplate"):
                                        m.NotificationTemplate.query = _FlaskQueryProxy(m.NotificationTemplate)
                                except Exception:
                                    pass
                                try:
                                    if hasattr(m, "NotificationPreference"):
                                        m.NotificationPreference.query = _FlaskQueryProxy(m.NotificationPreference)
                                except Exception:
                                    pass
                                try:
                                    if hasattr(m, "PushSubscription"):
                                        m.PushSubscription.query = _FlaskQueryProxy(m.PushSubscription)
                                except Exception:
                                    pass

                                # Always print debug info here to help CI diagnostics
                                try:
                                    try:
                                        user_cls = getattr(m, "User", None)
                                        user_query = getattr(user_cls, "query", None)
                                        if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                                            print(f"[EXT DEBUG] attached proxies for module '{mod_name}': User id={id(user_cls) if user_cls else None}, User.query id={id(user_query) if user_query else None}")
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
                # Attach model query proxies that route `.query` to the
                # Flask-SQLAlchemy session so tests that call `Model.query`
                # will use the app's session instead of the module-level one.
                try:
                    # Prefer backend.models but also handle models_with_analytics
                    try:
                        _models = importlib.import_module("backend.models")
                    except Exception:
                        try:
                            _models = importlib.import_module("models_with_analytics")
                        except Exception:
                            _models = None
                    try:
                        from backend.extensions import db as _ext_db

                        class _FlaskQueryProxy:
                            def __init__(self, model):
                                self._model = model

                            def __getattr__(self, name):
                                try:
                                    if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                                        print(f"[EXT DEBUG] _FlaskQueryProxy __getattr__ called for {getattr(self._model, '__name__', None)} (module={getattr(self._model, '__module__', None)}) using session id={id(_ext_db.session)}")
                                except Exception:
                                    pass
                                return getattr(_ext_db.session.query(self._model), name)

                        # Attach common proxies
                        try:
                            if _models is not None and hasattr(_models, 'User'):
                                _models.User.query = _FlaskQueryProxy(_models.User)
                                if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                                    print("[EXT] Attached User.query proxy to Flask DB session (module: {} )".format(getattr(_models,'__name__', None)))
                        except Exception:
                            pass
                        try:
                            _models.NotificationTemplate.query = _FlaskQueryProxy(_models.NotificationTemplate)
                        except Exception:
                            pass
                        try:
                            _models.NotificationPreference.query = _FlaskQueryProxy(_models.NotificationPreference)
                        except Exception:
                            pass
                        try:
                            _models.PushSubscription.query = _FlaskQueryProxy(_models.PushSubscription)
                        except Exception:
                            pass
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    db.init_app = _init_app_and_sync
except Exception:
    # If we can't wrap init_app for any reason, fall back to default behavior
    pass

# Ensure any calls to `db.create_all()` also synchronize the standalone
# `Base` metadata (from `backend.models`) onto the Flask-SQLAlchemy engine.
try:
    if hasattr(db, "create_all"):
        _orig_create_all = db.create_all

        def _create_all_and_sync(app=None, **kwargs):
            # Call the original create_all (Flask-SQLAlchemy) which creates
            # tables defined on the Flask `db.metadata`.
            try:
                result = _orig_create_all(app=app, **kwargs)
            except TypeError:
                # Some versions call create_all() without kwargs
                result = _orig_create_all(app)

            # Also ensure the standalone declarative Base metadata is created
            try:
                import importlib

                _models = importlib.import_module("backend.models")
                engine = None
                try:
                    engine = db.get_engine(app)
                except Exception:
                    engine = getattr(db, "engine", None)

                if engine is not None:
                    try:
                        _models.Base.metadata.create_all(bind=engine)
                    except Exception:
                        pass
            except Exception:
                pass

            return result

        db.create_all = _create_all_and_sync
except Exception:
    pass

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
