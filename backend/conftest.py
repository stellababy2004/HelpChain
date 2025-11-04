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
from sqlalchemy.pool import StaticPool

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
                # Import the application module and seed the default admin if needed.
                import appy as _appy

                try:
                    _appy.initialize_default_admin()
                except Exception:
                    # If seeding fails, tests may create an admin explicitly; do not raise.
                    try:
                        logging.getLogger(__name__).exception(
                            "initialize_default_admin() failed in setup_schema_and_admin"
                        )
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


@pytest.fixture(scope="session", autouse=True)
def setup_models():
    """Setup models before any tests run"""
    try:
        import models_with_analytics  # noqa: F401
    except ImportError:
        pass


@pytest.fixture(scope="session", autouse=True)
def app():
    """Create and configure a test app instance. Sets up schema."""
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

    from appy import app as real_app

    try:
        from extensions import login_manager  # type: ignore[import-not-found]
    except Exception:
        from helpchain_backend.src.extensions import login_manager
    from helpchain_backend.src.routes.admin import admin_bp

    if "admin" not in real_app.blueprints:
        real_app.register_blueprint(admin_bp, url_prefix="/admin")
    if not hasattr(real_app, "login_manager"):
        login_manager.init_app(real_app)
        real_app.login_manager = login_manager
    from models import AdminUser

    @login_manager.user_loader
    def load_user(user_id):
        return AdminUser.query.get(int(user_id))

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
    real_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    real_app.config["_TEST_DB_FD"] = db_fd
    real_app.config["_TEST_DB_PATH"] = db_path
    real_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
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
    return real_app


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
                    row = db.session.execute(
                        "SELECT id FROM admin_users LIMIT 1"
                    ).fetchone()
                    if row:
                        admin_id = int(row[0])
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

    # (премахнато: дефиниция без тяло)
