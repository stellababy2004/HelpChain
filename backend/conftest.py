import pytest


# Provides a db_session fixture for tests that need direct DB access.
@pytest.fixture(scope="function")
def db_session(app):
    """Yields the canonical SQLAlchemy session for the test DB.

    Simplified: avoid nested savepoint transactions (db.session.begin_nested()).
    Many SQLite savepoint errors were caused by mixing separate engines/connections
    or creating nested savepoints. Instead we yield the app's session and perform
    a rollback + cleanup after the test. If `db.session` exposes `remove()` we
    call it to properly clear the scoped session; otherwise we close/expunge.
    """

    from appy import db

    with app.app_context():
        sess = db.session
        try:
            yield sess
        finally:
            # Try a safe rollback and session cleanup. Use `remove()` for scoped sessions
            try:
                sess.rollback()
            except Exception:
                pass
            try:
                # scoped_session exposes remove()
                if hasattr(db.session, "remove"):
                    db.session.remove()  # type: ignore[attr-defined]
                else:
                    try:
                        sess.expunge_all()
                    except Exception:
                        pass
                    try:
                        sess.close()
                    except Exception:
                        pass
            except Exception:
                pass


import logging
import os
import sys
import warnings
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
from sqlalchemy.pool import NullPool, StaticPool

# Ensure appy.py sees we're running tests when it's imported.
# This must be set before importing `appy` in fixtures so the module
# uses the TESTING branch for DB initialization.
os.environ.setdefault("HELPCHAIN_TESTING", "1")
# For stable test databases, create a temp sqlite file early and expose
# its path via an environment variable so app initialization will pick it up
# and create the SQLAlchemy engine against a file-backed DB (avoids
# SQLite in-memory per-connection visibility issues in tests).
try:
    import tempfile as _tempfile

    _fd, _path = _tempfile.mkstemp(suffix="_test.db")
    # store so appy.py can detect the test DB path at import time
    os.environ.setdefault("HELPCHAIN_TEST_DB_PATH", _path)
    os.environ.setdefault("HELPCHAIN_TEST_DB_FD", str(_fd))
except Exception:
    # If tempfile creation fails for any reason, continue without setting
    # the env var; appy will fall back to in-memory DB for tests.
    pass

# Optional: start tracemalloc early when requested so we can later
# obtain exact allocation tracebacks for live DBAPI objects. Enable by
# setting HELPCHAIN_TEST_TRACEMALLOC=1 in the environment before running
# pytest. We keep a module-level flag `_TRACEMALLOC_ACTIVE` for checks.
try:
    if os.environ.get("HELPCHAIN_TEST_TRACEMALLOC") == "1":
        try:
            import tracemalloc as _tracemalloc

            # Record a deeper stack (25 frames) to make sure we capture
            # application-level callsites such as lines inside appy.py.
            _tracemalloc.start(25)
            _TRACEMALLOC_ACTIVE = True
        except Exception:
            _TRACEMALLOC_ACTIVE = False
    else:
        _TRACEMALLOC_ACTIVE = False
except Exception:
    _TRACEMALLOC_ACTIVE = False


# Early, module-level network and SMTP blocking to prevent import-time
# connections during pytest collection. Some modules may perform network
# I/O at import time; fixture-level patches run too late to stop those and
# can lead to unclosed SSL sockets. Apply only when running tests.
try:
    if os.environ.get("HELPCHAIN_TESTING") == "1":
        try:
            import socket as _socket

            # Replace create_connection early so imports can't open sockets.
            _CONFTST_ORIG_CREATE_CONN = getattr(_socket, "create_connection", None)

            def _blocked_create(addr, timeout=None, source_address=None):
                raise OSError("Network calls are blocked during tests (early patch)")

            try:
                _socket.create_connection = _blocked_create
            except Exception:
                pass
        except Exception:
            pass

        try:
            import smtplib as _smtplib

            class _DummySMTP:
                def __init__(self, *args, **kwargs):
                    self.args = args

                def sendmail(self, *args, **kwargs):
                    return {}

                def ehlo(self):
                    return

                def login(self, *args, **kwargs):
                    return

                def starttls(self, *args, **kwargs):
                    return

                def quit(self):
                    return

                def close(self):
                    return

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            try:
                _smtplib.SMTP = _DummySMTP
                _smtplib.SMTP_SSL = _DummySMTP
            except Exception:
                pass
        except Exception:
            pass
except Exception:
    # Best-effort early patch; don't fail test collection if anything goes wrong.
    pass


# Optional: debug helper that wraps sqlite3.connect to print a Python stack
# at allocation time. This is only imported when HELPCHAIN_TEST_DEBUG=1 so
# it won't affect normal test runs. For focused, clean diagnostic runs we
# allow suppressing this helper by setting
# HELPCHAIN_TEST_DEBUG_SUPPRESS_DEBUG_SQLITE=1 in the environment.
try:
    if (
        os.environ.get("HELPCHAIN_TEST_DEBUG") == "1"
        and os.environ.get("HELPCHAIN_TEST_DEBUG_SUPPRESS_DEBUG_SQLITE") != "1"
    ):
        try:
            import debug_sqlite_connect  # noqa: F401
        except Exception:
            # Best-effort; don't fail collection if debug helper cannot be imported
            pass
except Exception:
    pass

# Test-only: wrap sqlite3.connect in the test process to record allocation
# frames for any DBAPI connection that is opened. This is a best-effort
# diagnostic helper that writes candidate application frames to
# backend/tools/traced_candidates.txt when HELPCHAIN_TEST_DEBUG=1.
# The wrapper can be suppressed by setting HELPCHAIN_TEST_DEBUG_SUPPRESS_SQLITE_WRAP=1
# so we can run cleaner diagnostic passes when needed.
try:
    if (
        os.environ.get("HELPCHAIN_TEST_DEBUG") == "1"
        and os.environ.get("HELPCHAIN_TEST_DEBUG_SUPPRESS_SQLITE_WRAP") != "1"
    ):
        try:
            import sqlite3 as _sqlite
            import traceback as _traceback
            from pathlib import Path as _Path

            _tools_fn = (
                _Path(__file__).resolve().parent / "tools" / "traced_candidates.txt"
            )

            _orig_sqlite_connect = getattr(_sqlite, "connect", None)
            _orig_dbapi2_connect = None
            try:
                _orig_dbapi2_connect = getattr(_sqlite, "dbapi2", None)
                if _orig_dbapi2_connect is not None and hasattr(
                    _orig_dbapi2_connect, "connect"
                ):
                    _orig_dbapi2_connect = _orig_dbapi2_connect.connect
                else:
                    _orig_dbapi2_connect = None
            except Exception:
                _orig_dbapi2_connect = None

            def _dbg_connect(*a, **kw):
                try:
                    # Capture current stack and try to find first frame inside repo
                    stack = _traceback.extract_stack(limit=30)
                    repo_root = _Path(__file__).resolve().parent
                    candidate = None
                    for fr in reversed(stack):
                        try:
                            fpath = _Path(fr.filename).resolve()
                            # Skip frames originating from this conftest/debug helpers
                            # or the tools/ folder so we capture the first application
                            # frame instead of the wrapper itself.
                            try:
                                if fpath.samefile(_Path(__file__).resolve()):
                                    continue
                            except Exception:
                                pass
                            # Skip any frame whose path mentions conftest.py explicitly
                            try:
                                if "conftest.py" in str(fpath):
                                    continue
                            except Exception:
                                pass
                            # Skip debug helper modules and anything inside tools/
                            parts = list(fpath.parts)
                            name = fpath.name
                            if name.startswith("debug_") or "tools" in parts:
                                continue
                            if str(fpath).startswith(str(repo_root)):
                                candidate = (str(fpath), fr.lineno)
                                break
                        except Exception:
                            continue
                    if candidate:
                        try:
                            _tools_fn.parent.mkdir(parents=True, exist_ok=True)
                            # Write candidate but avoid duplicate consecutive entries
                            try:
                                last = None
                                if _tools_fn.exists():
                                    with _tools_fn.open("r", encoding="utf-8") as _r:
                                        lines = _r.readlines()
                                        if lines:
                                            last = lines[-1].rstrip("\n")
                                entry = f"{candidate[0]}:{candidate[1]}"
                                if last != entry:
                                    with _tools_fn.open("a", encoding="utf-8") as _f:
                                        _f.write(entry + "\n")
                            except Exception:
                                # Best-effort append on any failure
                                try:
                                    with _tools_fn.open("a", encoding="utf-8") as _f:
                                        _f.write(f"{candidate[0]}:{candidate[1]}\n")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                # Delegate to original connect(s)
                if _orig_sqlite_connect is not None:
                    return _orig_sqlite_connect(*a, **kw)
                if _orig_dbapi2_connect is not None:
                    return _orig_dbapi2_connect(*a, **kw)
                # Fallback: raise
                raise RuntimeError("no sqlite connect function to delegate to")

            try:
                if _orig_sqlite_connect is not None:
                    _sqlite.connect = _dbg_connect
                try:
                    dbapi2 = getattr(_sqlite, "dbapi2", None)
                    if dbapi2 is not None and hasattr(dbapi2, "connect"):
                        dbapi2.connect = _dbg_connect
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass
except Exception:
    pass

# Test-only: wrap SQLAlchemy dialect connect to capture allocation frames
# The dialect wrapper can be suppressed by setting
# HELPCHAIN_TEST_DEBUG_SUPPRESS_DIALECT_WRAP=1 to reduce diagnostic noise.
try:
    if (
        os.environ.get("HELPCHAIN_TEST_DEBUG") == "1"
        and os.environ.get("HELPCHAIN_TEST_DEBUG_SUPPRESS_DIALECT_WRAP") != "1"
    ):
        try:
            import traceback as _traceback
            from pathlib import Path as _Path

            import sqlalchemy.engine.default as _sqldef

            _tools_fn2 = (
                _Path(__file__).resolve().parent / "tools" / "traced_candidates.txt"
            )
            _orig_dialect_connect = getattr(_sqldef.DefaultDialect, "connect", None)

            def _wrapped_dialect_connect(self, *args, **kwargs):
                try:
                    stack = _traceback.extract_stack(limit=40)
                    repo_root = _Path(__file__).resolve().parent
                    candidate = None
                    for fr in reversed(stack):
                        try:
                            fpath = _Path(fr.filename).resolve()
                            # Do not record frames that belong to this conftest or
                            # diagnostic/debug modules. Prefer the first user
                            # application frame inside the repo directory.
                            try:
                                if fpath.samefile(_Path(__file__).resolve()):
                                    continue
                            except Exception:
                                pass
                            try:
                                if "conftest.py" in str(fpath):
                                    continue
                            except Exception:
                                pass
                            parts = list(fpath.parts)
                            name = fpath.name
                            if name.startswith("debug_") or "tools" in parts:
                                continue
                            if str(fpath).startswith(str(repo_root)):
                                candidate = (str(fpath), fr.lineno)
                                break
                        except Exception:
                            continue
                    if candidate:
                        try:
                            _tools_fn2.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                last = None
                                if _tools_fn2.exists():
                                    with _tools_fn2.open("r", encoding="utf-8") as _r:
                                        lines = _r.readlines()
                                        if lines:
                                            last = lines[-1].rstrip("\n")
                                entry = f"{candidate[0]}:{candidate[1]}"
                                if last != entry:
                                    with _tools_fn2.open("a", encoding="utf-8") as _f:
                                        _f.write(entry + "\n")
                            except Exception:
                                try:
                                    with _tools_fn2.open("a", encoding="utf-8") as _f:
                                        _f.write(f"{candidate[0]}:{candidate[1]}\n")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                if _orig_dialect_connect is not None:
                    return _orig_dialect_connect(self, *args, **kwargs)
                raise RuntimeError("no dialect connect available")

            try:
                if _orig_dialect_connect is not None:
                    _sqldef.DefaultDialect.connect = _wrapped_dialect_connect
            except Exception:
                pass
        except Exception:
            pass
except Exception:
    pass

# Test-only: wrap Engine.connect to capture allocation frames at the
# SQLAlchemy Engine boundary. This helps find the application frame that
# triggered SQLAlchemy to open a DBAPI connection.
#
# The wrapper can be suppressed for a focused test run by setting
# HELPCHAIN_TEST_DEBUG_SUPPRESS_ENGINE_WRAP=1 in the environment. This
# allows us to reduce diagnostic noise from our own wrapper when
# measuring app-level allocation hotspots.
try:
    if (
        os.environ.get("HELPCHAIN_TEST_DEBUG") == "1"
        and os.environ.get("HELPCHAIN_TEST_DEBUG_SUPPRESS_ENGINE_WRAP") != "1"
    ):
        try:
            import traceback as _traceback
            from pathlib import Path as _Path

            import sqlalchemy.engine.base as _sqbase

            _tools_fn3 = (
                _Path(__file__).resolve().parent / "tools" / "traced_candidates.txt"
            )
            _orig_engine_connect = getattr(_sqbase.Engine, "connect", None)

            def _wrapped_engine_connect(self, *args, **kwargs):
                try:
                    stack = _traceback.extract_stack(limit=60)
                    repo_root = _Path(__file__).resolve().parent
                    candidate = None
                    for fr in reversed(stack):
                        try:
                            fpath = _Path(fr.filename).resolve()
                            # skip conftest, debug helpers, tools and virtualenv/site-packages
                            try:
                                if fpath.samefile(_Path(__file__).resolve()):
                                    continue
                            except Exception:
                                pass
                            try:
                                if "conftest.py" in str(fpath):
                                    continue
                            except Exception:
                                pass
                            parts = list(fpath.parts)
                            name = fpath.name
                            if name.startswith("debug_") or "tools" in parts:
                                continue
                            # skip installed packages
                            if any(
                                p in str(fpath)
                                for p in ("site-packages", ".venv", "dist-packages")
                            ):
                                continue
                            if str(fpath).startswith(str(repo_root)):
                                candidate = (str(fpath), fr.lineno)
                                break
                        except Exception:
                            continue
                    if candidate:
                        try:
                            _tools_fn3.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                last = None
                                if _tools_fn3.exists():
                                    with _tools_fn3.open("r", encoding="utf-8") as _r:
                                        lines = _r.readlines()
                                        if lines:
                                            last = lines[-1].rstrip("\n")
                                entry = f"{candidate[0]}:{candidate[1]}"
                                if last != entry:
                                    with _tools_fn3.open("a", encoding="utf-8") as _f:
                                        _f.write(entry + "\n")
                            except Exception:
                                try:
                                    with _tools_fn3.open("a", encoding="utf-8") as _f:
                                        _f.write(f"{candidate[0]}:{candidate[1]}\n")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                if _orig_engine_connect is not None:
                    return _orig_engine_connect(self, *args, **kwargs)
                raise RuntimeError("no Engine.connect available")

            try:
                if _orig_engine_connect is not None:
                    _sqbase.Engine.connect = _wrapped_engine_connect
            except Exception:
                pass
        except Exception:
            pass
except Exception:
    pass


# NOTE: Avoid importing models at module import time here. Importing them
# before the test fixtures run can cause the same module to be loaded under
# different names/paths (due to sys.path manipulations) which leads to
# SQLAlchemy metadata being registered twice and duplicate index/table
# creation errors. Models are imported explicitly inside fixtures where
# the app/sys.path is already configured.
@pytest.fixture(autouse=True)
def setup_schema_and_admin(app):
    """Autouse fixture that runs after the `app` fixture has created the schema.

    We depend on the session-scoped `app` fixture so that `db.create_all()` has
    already run. This avoids importing `appy` (which could trigger initialization
    logic) before the test DB schema exists and prevents "no such table" errors.
    """
    try:
        # `app` is the Flask app instance returned by the session-scoped fixture.
        with app.app_context():
            try:
                # Import the application module. Seeding the default admin is
                # handled centrally by the session-scoped `app` fixture; avoid
                # running per-test seeding which can trigger repeated DB connects.
                # Avoid importing `appy` here. Importing it per-test can
                # trigger module-level initialization (including
                # initialize_default_admin) which we want to run only once
                # in the session-scoped `app` fixture. If `appy` is already
                # loaded by the session fixture, reference it from sys.modules
                # so we can prime its caches without re-importing it.
                try:
                    _appy = sys.modules.get("appy")
                except Exception:
                    _appy = None
                # Test-only optimization: prime the appy._table_exists_cache so that
                # subsequent calls to _has_table() during the test session do not
                # repeatedly create Inspector/Connection objects. This is a
                # best-effort, low-risk optimization and only runs when the Flask
                # app is in TESTING mode.
                try:
                    try:
                        from flask import current_app

                        if getattr(current_app, "config", {}).get("TESTING"):
                            try:
                                if getattr(_appy, "_table_exists_cache", None) is None:
                                    _appy._table_exists_cache = {}
                                # We know we've just created the schema above; mark
                                # the admin_users table as present to avoid forcing
                                # additional inspector calls during tests.
                                try:
                                    _appy._table_exists_cache["admin_users"] = True
                                except Exception:
                                    pass
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                # If appy cannot be imported for some reason, skip auto-seeding for this test.
                pass
    except Exception:
        # Silently continue; some tests create their own admin users.
        pass


import logging
import os
import sys
import warnings
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest
from sqlalchemy.pool import StaticPool

# Добавяме helpchain-backend (родител на папката src) в началото на sys.path,
# за да може `import src` да работи
_root = os.path.dirname(__file__)
_src_parent = os.path.join(_root, "helpchain-backend")
if os.path.isdir(_src_parent):
    sys.path.insert(0, _src_parent)

# Добавя текущата папка (backend) в sys.path така че 'appy' да се импортира директно
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Early: ensure canonical extensions is present under common names before any
# model modules are imported. This prevents model modules from creating their
# own SQLAlchemy() instances by importing a shim that instantiates one.
try:
    import importlib

    try:
        canonical_ext = importlib.import_module("backend.extensions")
    except Exception:
        try:
            canonical_ext = importlib.import_module("extensions")
        except Exception:
            canonical_ext = None

    if canonical_ext is not None:
        # Force the canonical extensions module into the common import names so
        # subsequent imports will use its SQLAlchemy() instance. Overriding any
        # pre-existing module is intentional here (tests run in an isolated
        # environment) to prevent duplicate SQLAlchemy instances.
        for alias in ("extensions", "backend.extensions"):
            sys.modules[alias] = canonical_ext

        # If any model modules were already imported (possibly bound to a
        # different SQLAlchemy instance), remove them so they can be re-imported
        # cleanly against the canonical db.
        for m in (
            "models",
            "backend.models",
            "helpchain_backend.src.models",
            "models_with_analytics",
            "backend.models_with_analytics",
            "helpchain_backend.src.models_with_analytics",
        ):
            if m in sys.modules:
                try:
                    del sys.modules[m]
                except Exception:
                    pass

        # Import canonical model modules now; they will bind to canonical_ext.db
        try:
            models_mod = importlib.import_module("backend.models")
            if models_mod is not None:
                for alias in (
                    "models",
                    "backend.models",
                    "helpchain_backend.src.models",
                ):
                    sys.modules[alias] = models_mod
        except Exception:
            pass

        try:
            analytics_mod = importlib.import_module("backend.models_with_analytics")
            if analytics_mod is not None:
                for alias in (
                    "models_with_analytics",
                    "backend.models_with_analytics",
                    "helpchain_backend.src.models_with_analytics",
                ):
                    sys.modules[alias] = analytics_mod
        except Exception:
            pass
except Exception:
    pass

# Import and alias analytics models early so the module is only loaded once
# under a single module object. Importing under multiple names (for example
# 'models_with_analytics' and 'backend.models_with_analytics') leads to SQLAlchemy
# registering duplicate mapped classes (same class name, different module)
# which triggers the "Multiple classes found for path 'Task'" error.
try:
    import importlib

    analytics_mod = None
    try:
        analytics_mod = importlib.import_module("models_with_analytics")
    except Exception:
        try:
            analytics_mod = importlib.import_module("backend.models_with_analytics")
        except Exception:
            try:
                analytics_mod = importlib.import_module(
                    "helpchain_backend.src.models_with_analytics"
                )
            except Exception:
                analytics_mod = None

    if analytics_mod is not None:
        # Ensure all common import names reference the same module object
        for alias in (
            "models_with_analytics",
            "backend.models_with_analytics",
            "helpchain_backend.src.models_with_analytics",
        ):
            if alias not in sys.modules:
                sys.modules[alias] = analytics_mod
except Exception:
    # best-effort; don't fail test collection if aliasing doesn't work
    pass

# Do NOT import `models_with_analytics` here under an arbitrary name. Importing
# the same module under both 'models_with_analytics' and 'backend.models_with_analytics'
# can cause SQLAlchemy to register identical mapped classes twice (same class
# name, different module objects) which triggers the "Multiple classes found"
# error. We delay importing analytics models until the `app` fixture where we
# can ensure a single canonical module object is used and alias sys.modules so
# both names reference the same module object.


def pytest_configure(config):
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("helpchain").setLevel(logging.ERROR)
    logging.getLogger("appy").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, module="sqlalchemy")
    # Suppress SQLAlchemy SAWarning about declarative base being replaced
    try:
        import sqlalchemy as _sqlalchemy

        warnings.filterwarnings("ignore", category=_sqlalchemy.exc.SAWarning)
    except Exception:
        pass
    # Default TTL for _has_table checks during tests to 30s. Tests can override
    # via the HELPCHAIN_HAS_TABLE_TTL environment variable if needed.
    try:
        import os

        os.environ.setdefault("HELPCHAIN_HAS_TABLE_TTL", "30")
    except Exception:
        pass
    # Ensure canonical extensions module is available under common names
    # before importing `appy` which imports models at module-import time.
    try:
        import importlib

        try:
            canonical_ext = importlib.import_module("backend.extensions")
        except Exception:
            try:
                canonical_ext = importlib.import_module("extensions")
            except Exception:
                canonical_ext = None

        if canonical_ext is not None:
            # Alias the top-level names to the canonical extensions module so
            # imports like `from extensions import db` resolve to the same object.
            for alias in ("extensions", "backend.extensions"):
                if alias not in sys.modules:
                    sys.modules[alias] = canonical_ext

            # If the shim package `helpchain_backend.src.extensions` exists,
            # import it now so it can attach lightweight objects like
            # `login_manager` while reusing the canonical `db` above. Do NOT
            # overwrite the shim name with the canonical module object since
            # the shim defines additional attributes the top-level module
            # does not (e.g. `login_manager`). Importing the shim after the
            # canonical module is in sys.modules ensures it will reuse the
            # same `db` instance rather than creating a second SQLAlchemy().
            try:
                shim = importlib.import_module("helpchain_backend.src.extensions")
                sys.modules["helpchain_backend.src.extensions"] = shim
            except Exception:
                # Not fatal: if the shim isn't present, some modules may import
                # login_manager from elsewhere; continue best-effort.
                pass
    except Exception:
        pass

@pytest.fixture(scope="session", autouse=True)
def app():
    """Create and configure a test app instance. Sets up schema."""
    from appy import app as real_app

    try:
        from extensions import login_manager  # type: ignore[import-not-found]
    except Exception:
        from helpchain_backend.src.extensions import login_manager
    from helpchain_backend.src.routes.admin import admin_bp

    if "admin" not in real_app.blueprints:
        real_app.register_blueprint(admin_bp, url_prefix="/admin")
    if not hasattr(real_app, "login_manager"):
        try:
            # Only call init_app if the application has not yet handled a request.
            # Calling init_app after the first request raises an AssertionError
            # in newer Flask versions (setup phase is finished). In that case
            # skip init_app but still attach the login_manager object so tests
            # that reference `app.login_manager` or decorate user_loader will
            # continue to work.
            if not getattr(real_app, "_got_first_request", False):
                login_manager.init_app(real_app)
            else:
                logging.getLogger(__name__).warning(
                    "Skipping login_manager.init_app() because app already handled a request"
                )
        except AssertionError:
            # Flask reported that setup is finished; skip initialization.
            logging.getLogger(__name__).warning(
                "login_manager.init_app() raised AssertionError; skipping initialization"
            )
        finally:
            # Ensure the app has a reference to the login manager instance.
            try:
                real_app.login_manager = login_manager
            except Exception:
                pass
    from models import AdminUser

    @login_manager.user_loader
    def load_user(user_id):
        # Use Session.get when available to avoid SQLAlchemy LegacyAPIWarning
        try:
            from appy import db as _db

            return _db.session.get(AdminUser, int(user_id))
        except Exception:
            try:
                # Fallback to session.get using the canonical db if possible
                from appy import db as _db_fallback

                return _db_fallback.session.get(AdminUser, int(user_id))
            except Exception:
                # If we cannot resolve the canonical db, return None rather than
                # falling back to the legacy Query.get API which emits warnings.
                return None

    real_app.config["TESTING"] = True
    real_app.config["WTF_CSRF_ENABLED"] = False
    real_app.config["EMAIL_2FA_ENABLED"] = real_app.config.get(
        "EMAIL_2FA_ENABLED", False
    )
    # Prefer a single session-wide test DB path set at module import time so
    # all fixtures and the app use the same SQLite file. If the env var was
    # already set above, reuse it. Otherwise create a new temp file.
    import tempfile

    db_fd = None
    db_path = os.environ.get("HELPCHAIN_TEST_DB_PATH")
    if not db_path:
        db_fd, db_path = tempfile.mkstemp(suffix="_test.db")
        os.environ.setdefault("HELPCHAIN_TEST_DB_PATH", db_path)
    else:
        # Ensure the directory for the configured test DB path exists
        try:
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
        except Exception:
            # If we cannot create the directory, let SQLAlchemy report the error
            pass
    real_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    real_app.config["_TEST_DB_FD"] = db_fd
    real_app.config["_TEST_DB_PATH"] = db_path
    # Prefer a test-friendly pool configuration. Use NullPool in TESTING to
    # avoid long-lived DBAPI connections being retained by a pool, which
    # reduces ResourceWarning noise during per-test teardown. StaticPool is
    # still acceptable for some SQLite test setups (single-file DB); choose
    # NullPool in tests unless overridden by environment.
    try:
        if os.environ.get("HELPCHAIN_TESTING") == "1":
            _poolclass = NullPool
        else:
            _poolclass = StaticPool
    except Exception:
        _poolclass = StaticPool

    real_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": _poolclass,
    }
    # Ensure the app-level SQLAlchemy engine is (re)registered using the
    # test-time engine options we just configured. Importing `appy` above
    # may have caused an engine to be created with the module defaults;
    # call the internal helper to re-register the engine so the
    # NullPool test setting takes effect immediately.
    try:
        import appy as _appy

        try:
            _appy._ensure_db_engine_registration()
        except Exception:
            # Best-effort: if the helper is not present or fails, continue
            # and let SQLAlchemy use whatever engine is currently registered.
            pass
    except Exception:
        pass

    from appy import db

    with real_app.app_context():
        # Ensure models (mappers) are imported so metadata includes all tables.
        # Try multiple candidate import paths and report failures for diagnostics.
        import importlib
        import importlib.machinery
        import importlib.util

        candidates = [
            "models",
            "backend.models",
            "helpchain_backend.src.models",
            "helpchain_backend.src.models.__init__",
        ]
        imported_any = False
        for cand in candidates:
            try:
                importlib.import_module(cand)
                imported_any = True
            except Exception as e:
                try:
                    logging.getLogger(__name__).debug(
                        f"models import candidate {cand} failed: {e}"
                    )
                except Exception:
                    pass

        # Also try models_with_analytics (analytics models) via a couple of paths
        analytics_candidates = [
            "models_with_analytics",
            "backend.models_with_analytics",
        ]
        for cand in analytics_candidates:
            try:
                importlib.import_module(cand)
            except Exception:
                try:
                    logging.getLogger(__name__).debug(f"analytics import {cand} failed")
                except Exception:
                    pass

        # Ensure the canonical extensions module is loaded and aliased so that
        # imports like `from extensions import db` inside model modules resolve
        # to the single shared `backend.extensions` instance. If the shim in
        # `helpchain_backend.src.extensions` runs before `backend.extensions` is
        # importable it may create a local SQLAlchemy() instance which leads to
        # duplicate registries and missing tables on the app's db.metadata.
        try:
            try:
                canonical_ext = importlib.import_module("backend.extensions")
            except Exception:
                # Try top-level name as a fallback
                canonical_ext = importlib.import_module("extensions")

            # Alias common import names to the canonical module object for
            # core names only; do not overwrite the shim module which
            # provides additional helpers such as `login_manager`.
            for alias in ("extensions", "backend.extensions"):
                if alias not in sys.modules:
                    sys.modules[alias] = canonical_ext

            # Import the shim module (if present) so attributes like
            # `login_manager` are available. Importing it after the canonical
            # module ensures it re-uses the same `db` instance.
            try:
                shim = importlib.import_module("helpchain_backend.src.extensions")
                sys.modules["helpchain_backend.src.extensions"] = shim
            except Exception:
                # Not fatal; continue.
                pass
        except Exception:
            # Best-effort; continue even if aliasing fails
            pass

        # If any model modules were imported earlier and are bound to a different
        # SQLAlchemy instance, unload and re-import them so they bind to the
        # canonical `db` from `canonical_ext`. This fixes the case where a
        # shim or alternate import path created its own SQLAlchemy() instance
        # and model classes were registered against the wrong metadata.
        try:
            canonical_db = (
                getattr(canonical_ext, "db", None)
                if "canonical_ext" in locals()
                else None
            )
            model_names_to_check = [
                "models",
                "backend.models",
                "helpchain_backend.src.models",
                "models_with_analytics",
                "backend.models_with_analytics",
                "helpchain_backend.src.models_with_analytics",
            ]
            for mod_name in list(model_names_to_check):
                try:
                    if mod_name in sys.modules and canonical_db is not None:
                        mod = sys.modules[mod_name]
                        mod_db = getattr(mod, "db", None)
                        if mod_db is not None and id(mod_db) != id(canonical_db):
                            # Unload and force re-import under the canonical extensions mapping
                            try:
                                del sys.modules[mod_name]
                            except Exception:
                                pass
                            try:
                                importlib.import_module(mod_name)
                                imported_any = True
                                logging.getLogger(__name__).debug(
                                    f"Re-imported {mod_name} against canonical db"
                                )
                            except Exception as e:
                                logging.getLogger(__name__).debug(
                                    f"Failed to re-import {mod_name}: {e}"
                                )
                except Exception:
                    # best-effort per-module; continue
                    pass
        except Exception:
            pass

        # If attempts to import the canonical model modules failed above, try
        # loading them directly from the repository files as a last-resort
        # fallback. This ensures the model classes/mappers are registered
        # with SQLAlchemy's metadata before calling create_all().
        try:
            if not imported_any:
                # Load top-level models.py by path
                models_path = os.path.join(HERE, "models.py")
                if os.path.exists(models_path):
                    try:
                        loader = importlib.machinery.SourceFileLoader(
                            "models", models_path
                        )
                        spec = importlib.util.spec_from_loader(loader.name, loader)
                        module = importlib.util.module_from_spec(spec)
                        loader.exec_module(module)
                        sys.modules["models"] = module
                        imported_any = True
                        logging.getLogger(__name__).debug(
                            f"Loaded models from {models_path}"
                        )
                    except Exception as e:
                        logging.getLogger(__name__).exception(
                            f"Failed to load models.py from {models_path}: {e}"
                        )

                # Also attempt to load models_with_analytics by path if present
                analytics_path = os.path.join(HERE, "models_with_analytics.py")
                if (
                    os.path.exists(analytics_path)
                    and "models_with_analytics" not in sys.modules
                ):
                    try:
                        loader = importlib.machinery.SourceFileLoader(
                            "models_with_analytics", analytics_path
                        )
                        spec = importlib.util.spec_from_loader(loader.name, loader)
                        module = importlib.util.module_from_spec(spec)
                        loader.exec_module(module)
                        sys.modules["models_with_analytics"] = module
                        logging.getLogger(__name__).debug(
                            f"Loaded models_with_analytics from {analytics_path}"
                        )
                    except Exception:
                        logging.getLogger(__name__).exception(
                            f"Failed to load models_with_analytics from {analytics_path}"
                        )
        except Exception:
            # Best-effort fallback; do not raise during test setup
            pass

        # Ensure both import names point to the same module object. This prevents
        # the same file being loaded twice under two different module names
        # (e.g. 'models_with_analytics' and 'backend.models_with_analytics') which
        # would create duplicate mapped classes in SQLAlchemy's registry.
        try:
            if (
                "backend.models_with_analytics" in sys.modules
                and "models_with_analytics" not in sys.modules
            ):
                sys.modules["models_with_analytics"] = sys.modules[
                    "backend.models_with_analytics"
                ]
            elif (
                "models_with_analytics" in sys.modules
                and "backend.models_with_analytics" not in sys.modules
            ):
                sys.modules["backend.models_with_analytics"] = sys.modules[
                    "models_with_analytics"
                ]
        except Exception:
            # best-effort aliasing; continue even if this fails
            pass

            # Optional diagnostics: enabled when HELPCHAIN_TEST_DEBUG=1.
        try:
            if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                model_names = [
                    "models",
                    "backend.models",
                    "helpchain_backend.src.models",
                    "models_with_analytics",
                    "backend.models_with_analytics",
                    "helpchain_backend.src.models_with_analytics",
                ]
                present = {name: (name in sys.modules) for name in model_names}
                print("[TEST DEBUG] model import presence:", present)
                try:
                    from models import AdminUser  # type: ignore

                    has_admin = True
                except Exception:
                    try:
                        from helpchain_backend.src.models import AdminUser  # type: ignore

                        has_admin = True
                    except Exception:
                        has_admin = False
                try:
                    from models_with_analytics import AnalyticsEvent  # type: ignore

                    has_analytics = True
                except Exception:
                    try:
                        from backend.models_with_analytics import AnalyticsEvent  # type: ignore

                        has_analytics = True
                    except Exception:
                        has_analytics = False
                print(
                    f"[TEST DEBUG] AdminUser importable: {has_admin}, AnalyticsEvent importable: {has_analytics}"
                )
                try:
                    metadata_tables = sorted(list(db.metadata.tables.keys()))
                except Exception:
                    metadata_tables = None
                print(
                    f"[TEST DEBUG] SQLAlchemy metadata tables before create_all: {metadata_tables}"
                )
        except Exception:
            # Diagnostics must not break test setup
            pass

        # Ensure the application's model modules are imported and bound to the
        # canonical `extensions.db` instance before we create the schema. In
        # some test collection environments model modules may not have been
        # imported (or were imported against a different SQLAlchemy instance),
        # which leads to missing tables in `db.metadata` and subsequent
        # OperationalError during tests. Import and alias common module names
        # here as a best-effort fix.
        try:
            import importlib

            for modname in (
                "backend.models",
                "models",
                "helpchain_backend.src.models",
            ):
                try:
                    m = importlib.import_module(modname)
                    # Alias the loaded module under common names so subsequent
                    # imports resolve to the same module object.
                    for alias in (
                        "models",
                        "backend.models",
                        "helpchain_backend.src.models",
                    ):
                        if alias not in sys.modules:
                            sys.modules[alias] = m
                except Exception:
                    # Continue; some import paths are optional in different
                    # dev/test layouts.
                    pass

            for modname in (
                "backend.models_with_analytics",
                "models_with_analytics",
                "helpchain_backend.src.models_with_analytics",
            ):
                try:
                    m = importlib.import_module(modname)
                    for alias in (
                        "models_with_analytics",
                        "backend.models_with_analytics",
                        "helpchain_backend.src.models_with_analytics",
                    ):
                        if alias not in sys.modules:
                            sys.modules[alias] = m
                except Exception:
                    pass
        except Exception:
            pass

        # Diagnostic: show what tables SQLAlchemy thinks are present before
        # attempting create_all(). Helpful when debugging missing-table issues.
        try:
            if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                try:
                    metadata_tables = sorted(list(db.metadata.tables.keys()))
                except Exception:
                    metadata_tables = None
                print(
                    f"[TEST DEBUG] SQLAlchemy metadata tables before create_all (post-import): {metadata_tables}"
                )
        except Exception:
            pass

        db.drop_all()
        db.create_all()
        # Ensure default admin is created immediately after schema creation
        # so tests depending on admin login see the user.
        try:
            import appy as _appy

            try:
                _appy.initialize_default_admin()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Default admin seed failed in app fixture"
                )
        except Exception:
            # If importing appy fails for any reason, continue; tests may seed per-fixture
            pass
    # Yield the app so we can perform session-scoped cleanup after the
    # entire test session finishes (dispose engines, remove sessions and
    # optionally delete temporary test DB file).
    try:
        yield real_app
    finally:
        try:
            from appy import db as _db

            try:
                if hasattr(_db.session, "remove"):
                    _db.session.remove()
                else:
                    try:
                        _db.session.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if getattr(_db, "engine", None) is not None:
                    _db.engine.dispose()
                    # Best-effort: some SQLAlchemy versions expose the Pool
                    # object at engine.pool. Calling its dispose() can more
                    # aggressively close DBAPI connections held by the pool
                    # and reduce ResourceWarning noise during test teardown.
                    try:
                        pool = getattr(_db.engine, "pool", None)
                        if pool is not None and hasattr(pool, "dispose"):
                            try:
                                pool.dispose()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        import gc as _gc

                        _gc.collect()
                    except Exception:
                        pass
                    # Run garbage collection to force DBAPI finalizers to run
                    # promptly during teardown. This helps prevent ResourceWarning
                    # messages about unclosed sqlite3.Connection objects that may
                    # only appear when finalizers run at process exit.
                    try:
                        import gc as _gc

                        _gc.collect()
                    except Exception:
                        pass
                    # Defensive: after disposing the engine, attempt to close any
                    # lingering sqlite3.Connection objects found by the GC. This
                    # is a best-effort measure to reduce ResourceWarning noise in
                    # test runs where DBAPI connections remain reachable to the
                    # Python runtime (for example, held by library internals).
                    try:
                        import gc as _gc2
                        import sqlite3 as _sqlite

                        conns = [
                            o
                            for o in _gc2.get_objects()
                            if isinstance(o, _sqlite.Connection)
                        ]
                        for c in conns:
                            try:
                                c.close()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Best-effort: close any lingering SQLAlchemy Connection objects
                    try:
                        import gc as _gc3

                        _sqlalchemy_conns = []
                        for o in _gc3.get_objects():
                            try:
                                tname = getattr(type(o), "__name__", "")
                                tmod = getattr(type(o), "__module__", "")
                                # Detect SQLAlchemy Connection objects conservatively
                                if tname == "Connection" and tmod.startswith(
                                    "sqlalchemy."
                                ):
                                    _sqlalchemy_conns.append(o)
                            except Exception:
                                continue
                        for _c in _sqlalchemy_conns:
                            try:
                                # Connection.close() will return DBAPI connection to pool
                                _c.close()
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            # If appy/db cannot be imported at teardown, ignore and continue
            pass

        # Clear any process-local table-existence caches from appy so state
        # does not leak between separate pytest runs. This clears the
        # preferred `_has_table` LRU cache via `_has_table_cache_clear()` if
        # present, and falls back to clearing the legacy `_table_exists_cache`
        # dict when necessary. This is defensive and swallows all errors.
        try:
            try:
                import appy as _appy_clear

                try:
                    clear_fn = getattr(_appy_clear, "_has_table_cache_clear", None)
                    if callable(clear_fn):
                        try:
                            clear_fn()
                        except Exception:
                            pass
                    else:
                        try:
                            if (
                                getattr(_appy_clear, "_table_exists_cache", None)
                                is not None
                            ):
                                try:
                                    _appy_clear._table_exists_cache.clear()
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

        # If a temporary test DB file was created by fixtures, attempt to
        # close its file descriptor and remove the file to avoid leaving
        # artifacts on the filesystem between runs.
        try:
            db_path = real_app.config.get("_TEST_DB_PATH")
            db_fd = real_app.config.get("_TEST_DB_FD")
            if db_fd:
                try:
                    import os as _os

                    try:
                        _os.close(int(db_fd))
                    except Exception:
                        pass
                except Exception:
                    pass
            if db_path and db_path.endswith("_test.db"):
                try:
                    import os as _os

                    if _os.path.exists(db_path):
                        try:
                            _os.remove(db_path)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass


@pytest.fixture
def set_pending_admin_session(app):
    """Helper to set the 'after-login' session state used by admin 2FA flows.

    Usage in tests:
        def test_x(client, set_pending_admin_session):
            set_pending_admin_session(client)

    This ensures `pending_email_2fa`, `pending_admin_id`, `email_2fa_code`,
    and `email_2fa_expires` are set inside the test client's session.
    The helper will create a minimal AdminUser if one does not exist.
    Returns a dict: {"admin_id": id, "code": code}
    """

    def _set(
        client,
        admin_username: str = "admin",
        code: str | None = None,
        expires_seconds: int = 300,
    ):
        # Resolve canonical db and AdminUser model via the app's context
        try:
            import appy as _appy

            db = _appy.db
        except Exception:
            try:
                from extensions import db  # type: ignore
            except Exception:
                from helpchain_backend.src.extensions import db as db  # type: ignore

        try:
            try:
                from models import AdminUser
            except Exception:
                from helpchain_backend.src.models import AdminUser  # type: ignore
        except Exception:
            AdminUser = None

        with client.application.app_context():
            admin_id = None
            if AdminUser is not None:
                try:
                    admin_obj = (
                        db.session.query(AdminUser)
                        .filter_by(username=admin_username)
                        .first()
                    )
                    if not admin_obj:
                        admin_obj = AdminUser(
                            username=admin_username,
                            email=f"{admin_username}@example.com",
                        )
                        try:
                            admin_obj.set_password("Admin123")
                        except Exception:
                            try:
                                from werkzeug.security import generate_password_hash

                                admin_obj.password_hash = generate_password_hash(
                                    "Admin123"
                                )
                            except Exception:
                                pass
                        db.session.add(admin_obj)
                        db.session.commit()
                    admin_id = getattr(admin_obj, "id", None)
                except Exception:
                    # best-effort: don't raise here; session keys will still be set
                    admin_id = None

            # If ORM lookup/creation failed (possible duplicate-mapper/class mismatch),
            # try a direct SQL lookup for an admin id to avoid relying on the model class.
            if admin_id is None:
                try:
                    _result = db.session.execute("SELECT id FROM admin_users LIMIT 1")
                    try:
                        row = _result.fetchone()
                        if row:
                            admin_id = int(row[0])
                    finally:
                        try:
                            _result.close()
                        except Exception:
                            pass
                except Exception:
                    # ignore and leave admin_id as None
                    pass

            # If ORM and simple SELECT failed to find/create an admin, do not
            # attempt raw SQL INSERT here anymore. Tests should prefer using the
            # ORM; fallbacks masked underlying issues and made tests less
            # deterministic. If we cannot find/create an admin via ORM or a
            # simple SELECT, leave admin_id as None and let the test decide.

        # Determine code if not provided
        if not code:
            try:
                import appy as _appy

                code = getattr(_appy, "generate_email_2fa_code", lambda: "123456")()
            except Exception:
                code = "123456"

        import time

        # Set session keys on the client session
        with client.session_transaction() as sess:
            sess["pending_email_2fa"] = True
            if admin_id is not None:
                sess["pending_admin_id"] = admin_id
            sess["email_2fa_code"] = code
            sess["email_2fa_expires"] = time.time() + int(expires_seconds)

        return {"admin_id": admin_id, "code": code}

    return _set


@pytest.fixture
def authenticated_admin_client(client, set_pending_admin_session):
    """Return a test client with an admin pending/active session set.

    Uses the `set_pending_admin_session` helper to ensure the client has
    the session keys expected by admin routes/tests.
    """
    info = set_pending_admin_session(client)

    # Also mark the test client as logged-in for Flask-Login protected routes.
    # Flask-Login stores the user id under the session key '_user_id'. We set
    # it here so decorators like @login_required will treat the client as
    # authenticated during tests. We also set '_fresh' to True for completeness.
    admin_id = info.get("admin_id") if isinstance(info, dict) else None
    if admin_id is not None:
        with client.session_transaction() as sess:
            try:
                sess["_user_id"] = str(admin_id)
                sess["_fresh"] = True
                # Some legacy checks inspect 'admin_logged_in' in session
                sess["admin_logged_in"] = True
            except Exception:
                pass

    return client


@pytest.fixture(autouse=True)
def _ensure_db_cleanup_after_test():
    """Autouse fixture: ensure SQLAlchemy sessions are removed and engine
    disposed after each test to avoid ResourceWarning about unclosed DB
    connections in pytest runs.

    This is defensive and best-effort: if the test does not import `appy`
    or `db` is not available we silently continue.
    """
    yield
    try:
        # Import canonical app module and db if available
        try:
            import appy as _appy

            _db = getattr(_appy, "db", None)
        except Exception:
            try:
                from extensions import db as _db  # type: ignore
            except Exception:
                try:
                    from helpchain_backend.src.extensions import db as _db  # type: ignore
                except Exception:
                    _db = None

        if _db is not None:
            try:
                if hasattr(_db.session, "remove"):
                    _db.session.remove()
                else:
                    try:
                        _db.session.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if getattr(_db, "engine", None) is not None:
                    _db.engine.dispose()
                    # Run GC to prompt DBAPI finalizers to run during test teardown
                    try:
                        import gc as _gc

                        _gc.collect()
                    except Exception:
                        pass
                    # Best-effort: close any lingering sqlite3.Connection objects
                    # found by the GC so ResourceWarning noise is reduced during
                    # pytest runs. This is a test-only, defensive measure and
                    # intentionally swallows exceptions.
                    try:
                        import gc as _gc2
                        import sqlite3 as _sqlite

                        conns = [
                            o
                            for o in _gc2.get_objects()
                            if isinstance(o, _sqlite.Connection)
                        ]
                        for c in conns:
                            try:
                                c.close()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Optional debug: if enabled, scan for live sqlite3.Connection
                    # objects and print allocation tracebacks to help locate leaks.
                    try:
                        import os as _os

                        if _os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                            try:
                                import gc as _gc2
                                import sqlite3 as _sqlite

                                # tracemalloc import/use is guarded by the module-level
                                # _TRACEMALLOC_ACTIVE flag which is set if HELPCHAIN_TEST_TRACEMALLOC=1

                                conns = [
                                    o
                                    for o in _gc2.get_objects()
                                    if isinstance(o, _sqlite.Connection)
                                ]
                                if conns:
                                    try:
                                        tools_dir = (
                                            Path(__file__).resolve().parent / "tools"
                                        )
                                        tools_dir.mkdir(parents=True, exist_ok=True)
                                        out_fn = (
                                            tools_dir
                                            / "tracemalloc_sqlite_connections.txt"
                                        )
                                    except Exception:
                                        out_fn = None

                                for c in conns:
                                    try:
                                        # Attempt to get a tracemalloc traceback for the object
                                        tb = None
                                        if globals().get("_TRACEMALLOC_ACTIVE"):
                                            try:
                                                import tracemalloc as _tracemalloc

                                                tb = _tracemalloc.get_object_traceback(
                                                    c
                                                )
                                            except Exception:
                                                tb = None

                                        # Write a durable record for post-mortem analysis
                                        try:
                                            if out_fn is not None:
                                                with out_fn.open(
                                                    "a", encoding="utf-8"
                                                ) as _out:
                                                    _out.write(
                                                        "--- sqlite3.Connection allocation ---\n"
                                                    )
                                                    _out.write(
                                                        f"object_id: {hex(id(c))}\n"
                                                    )
                                                    try:
                                                        _out.write(f"repr: {repr(c)}\n")
                                                    except Exception:
                                                        _out.write(
                                                            "repr: <unavailable>\n"
                                                        )
                                                    if tb:
                                                        try:
                                                            for line in tb.format():
                                                                _out.write(line + "\n")
                                                        except Exception:
                                                            _out.write(
                                                                "<failed to format tracemalloc trace>\n"
                                                            )
                                                    else:
                                                        _out.write(
                                                            "<no tracemalloc traceback available>\n"
                                                        )
                                                    _out.write("\n")
                                        except Exception:
                                            pass

                                        # Also emit to stdout for immediate visibility when running tests
                                        try:
                                            print(
                                                f"[TEST DEBUG] live sqlite3.Connection {hex(id(c))}"
                                            )
                                            if tb:
                                                try:
                                                    for frame in tb.format():
                                                        print(frame)
                                                except Exception:
                                                    pass
                                            else:
                                                print(
                                                    "[TEST DEBUG] no tracemalloc traceback available for this object"
                                                )
                                        except Exception:
                                            pass

                                        # Defensive: attempt to close lingering connections seen during tests
                                        try:
                                            c.close()
                                            print(
                                                f"[TEST DEBUG] closed sqlite3.Connection {hex(id(c))}"
                                            )
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
    except Exception:
        # Best-effort cleanup; do not raise during teardown
        pass


@pytest.fixture(autouse=True)
def _patch_flask_mail(mocker):
    """Patch flask_mail.Mail to a lightweight test-friendly class.

    Many code paths (including _dispatch_email) construct a local
    ``Mail(current_app)`` and call ``mail.send(msg)``. Tests historically
    patched `backend.appy.mail.send`, which doesn't catch the local Mail
    instance created inside _dispatch_email. To make mail behavior
    deterministic in tests we patch the `flask_mail.Mail` class so that
    its `send` records messages into `current_app.config['_sent_emails']`.

    This is a low-risk test-time shim that avoids touching production code
    and makes mail activity observable to tests.
    """

    class _TestMail:
        def __init__(self, app=None):
            self.app = app

        def send(self, msg):
            try:
                # If the main app exposes a mail instance, delegate to it so
                # tests that patch `backend.appy.mail.send` will trigger the
                # same behavior (including raised exceptions) and allow the
                # caller to exercise fallback paths.
                try:
                    import appy

                    appy_mail = getattr(appy, "mail", None)
                except Exception:
                    appy_mail = None

                if appy_mail is not None and hasattr(appy_mail, "send"):
                    # Delegate to the app's mail.send (may be patched by tests)
                    return appy_mail.send(msg)

                from flask import current_app

                lst = current_app.config.setdefault("_sent_emails", [])
                lst.append(msg)
            except Exception:
                # If current_app isn't available for some reason, swallow
                # the exception to avoid breaking tests that don't assert
                # on email behavior.
                pass

    # Patch the Mail class so imports like `from flask_mail import Mail`
    # will receive our test-friendly _TestMail.
    try:
        mocker.patch("flask_mail.Mail", _TestMail)
    except Exception:
        # If pytest-mock isn't available or patching fails, continue
        # without breaking test collection; some tests will still pass.
        pass

    yield

    # (премахнато: дефиниция без тяло)


@pytest.fixture(autouse=True)
def _safe_smtp_monkeypatch(mocker):
    """Autouse fixture: ensure tests don't open real SMTP/SSL sockets.

    Many code paths create `smtplib.SMTP` or `smtplib.SMTP_SSL` directly. To
    avoid intermittent ResourceWarning for unclosed SSL sockets during test
    runs, patch those classes to a lightweight dummy that implements the
    minimal API used by the code. Tests that need to assert SMTP behavior can
    still monkeypatch/override this fixture.
    """

    try:
        import smtplib as _smtplib

        class _DummySMTP:
            def __init__(self, *args, **kwargs):
                self.args = args

            def sendmail(self, *args, **kwargs):
                return {}

            def ehlo(self):
                return

            def login(self, *args, **kwargs):
                return

            def starttls(self, *args, **kwargs):
                return

            def quit(self):
                return

            def close(self):
                return

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        try:
            mocker.patch("smtplib.SMTP", _DummySMTP)
            mocker.patch("smtplib.SMTP_SSL", _DummySMTP)
        except Exception:
            # If pytest-mock isn't available or patching fails, continue.
            pass
        # Additionally, replace any module-level references to SMTP/SMTP_SSL
        # (for modules that did `from smtplib import SMTP_SSL`) by scanning
        # loaded modules and swapping attributes that come from smtplib.
        try:
            import smtplib as _smtplib
            import sys as _sys

            for _mod in list(_sys.modules.values()):
                try:
                    if _mod is None:
                        continue
                    for _attr in ("SMTP", "SMTP_SSL"):
                        if hasattr(_mod, _attr):
                            obj = getattr(_mod, _attr)
                            # If the object originates from smtplib, replace it
                            if getattr(obj, "__module__", None) == _smtplib.__name__:
                                try:
                                    setattr(_mod, _attr, _DummySMTP)
                                except Exception:
                                    pass
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass

    yield


@pytest.fixture(autouse=True)
def _block_network_calls():
    """Defensive fixture: block outgoing TCP connections during tests.

    This prevents accidental network I/O (SMTP, external APIs) from being
    performed by tests or library code. It's a last-resort safety net to avoid
    intermittent ResourceWarning about unclosed network sockets in CI.

    The implementation is best-effort and may be relaxed for tests that need
    network access (they can monkeypatch this fixture or set up explicit
    allowances).
    """

    try:
        import socket as _socket

        _orig_create = getattr(_socket, "create_connection", None)

        def _blocked_create(addr, timeout=None, source_address=None):
            raise OSError("Network calls are blocked during tests")

        try:
            _socket.create_connection = _blocked_create
        except Exception:
            pass
    except Exception:
        _orig_create = None

    yield

    # Restore original create_connection
    try:
        import socket as _socket

        if _orig_create is not None:
            try:
                _socket.create_connection = _orig_create
            except Exception:
                pass
    except Exception:
        pass
