import pytest

# Simple local conftest for tests folder to provide the `app` fixture used by
# pytest-flask. This keeps fixture discovery close to the tests and avoids
# surprises with conftest resolution order.

import os
import pathlib
import pytest
from datetime import datetime, timedelta

# Ensure a file-backed SQLite DATABASE_URL is set before importing the app.
# Import-time DATABASE_URL ensures the Flask app picks up the correct URI
# when it constructs the SQLAlchemy engine.
if not os.environ.get("DATABASE_URL"):
    db_path = pathlib.Path(__file__).parent.parent / "test_local.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

# Import the Flask app after DATABASE_URL is configured
from backend.appy import app as _appy


@pytest.fixture
def app():
    """Provide the Flask app for pytest-flask."""
    return _appy


@pytest.fixture
def db_session():
    """Yield a SQLAlchemy session for tests and rollback after each test."""
    from backend.extensions import db as _db

    sess = _db.session
    try:
        yield sess
    finally:
        try:
            sess.rollback()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clear_tables(app):
    """Autouse fixture to clear all rows between tests when using a
    persistent SQLite file DB.

    This avoids UNIQUE constraint collisions that occur when tests insert
    identical seed rows across multiple tests while using the same file DB.
    It deletes rows from every table in reverse dependency order so
    foreign key constraints are respected.
    """
    from backend.extensions import db as _db

    # Try to get the engine associated with the Flask app, fall back to
    # the DB instance engine attribute for older Flask-SQLAlchemy.
    try:
        engine = _db.get_engine(app)
    except Exception:
        engine = getattr(_db, "engine", None)

    # If no engine is available, just run the test normally.
    if engine is None:
        yield
        return

    # Do a quick pre-test cleanup so each test starts with an empty DB.
    conn = engine.connect()
    try:
        for table in reversed(list(getattr(_db.metadata, "sorted_tables", []))):
            conn.execute(table.delete())
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Run the test
    try:
        yield
    finally:
        # Post-test cleanup to ensure no leftover state for subsequent tests.
        conn2 = engine.connect()
        try:
            for table in reversed(list(getattr(_db.metadata, "sorted_tables", []))):
                conn2.execute(table.delete())
        finally:
            try:
                conn2.close()
            except Exception:
                pass
        # Ensure the scoped session is removed so next test starts fresh.
        try:
            _db.session.remove()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    """Create all tables for the test session and drop them afterwards.

    Import model modules first so SQLAlchemy MetaData contains all tables.
    """
    try:
        import backend.models as _models
        import backend.models_with_analytics as _models_analytics
    except Exception:
        # Let import errors surface during tests
        yield
        return

    from backend.extensions import db as _db
    from backend.appy import app as _appy

    with _appy.app_context():
        # Ensure the Flask app config explicitly uses the test DATABASE_URL
        try:
            test_db = os.environ.get("DATABASE_URL")
            if test_db:
                _appy.config["SQLALCHEMY_DATABASE_URI"] = test_db
                # Also set helper test path if code depends on it
                try:
                    # Try to extract file path for SQLite and set _TEST_DB_PATH
                    if test_db.startswith("sqlite:///"):
                        _appy.config["_TEST_DB_PATH"] = test_db.replace(
                            "sqlite:///", ""
                        )
                except Exception:
                    pass

        except Exception:
            pass

        # Try to force app-specific engine registration (internal helper)
        try:
            from backend import appy as _appy_mod

            if hasattr(_appy_mod, "_ensure_db_engine_registration"):
                _appy_mod._ensure_db_engine_registration()
        except Exception:
            pass

        # Diagnostics for debugging test DB issues and ensure we create the
        # tables on the exact engine the Flask app will use at request time.
        try:
            # Prefer the engine bound to the app (Flask-SQLAlchemy helper)
            try:
                engine = _db.get_engine(_appy)
            except Exception:
                # Fallback to attribute access if older Flask-SQLAlchemy
                engine = getattr(_db, "engine", None)

            print("[TEST DEBUG] engine (for create_all):", engine)
            print("[TEST DEBUG] db.session.bind:", getattr(_db.session, "bind", None))
            meta_tables_before = list(getattr(_db, "metadata", {}).tables.keys())
            print(
                "[TEST DEBUG] SQLAlchemy metadata tables before create_all:",
                meta_tables_before,
            )

            # Create all tables using the engine bound to the app so the
            # same SQLite file/connection is used for tests and request-time
            # DB access.
            # If other modules created their own SQLAlchemy() instance and
            # registered Table objects on a different MetaData, move those
            # tables into the canonical _db.metadata so create_all will
            # create them on the correct engine. This is defensive and
            # helps CI where import path duplication sometimes creates
            # multiple SQLAlchemy instances.
            try:
                import sys as _sys

                if getattr(_db, "metadata", None) is not None:
                    for _mod in list(_sys.modules.values()):
                        try:
                            _maybe_db = getattr(_mod, "db", None)
                        except Exception:
                            _maybe_db = None
                        if _maybe_db is None or id(_maybe_db) == id(_db):
                            continue
                        try:
                            _maybe_meta = getattr(_maybe_db, "metadata", None)
                            if not getattr(_maybe_meta, "tables", None):
                                continue
                            # Move any unknown tables into the canonical metadata
                            for _tbl in list(_maybe_meta.tables.values()):
                                try:
                                    if _tbl.name not in _db.metadata.tables:
                                        _tbl.tometadata(_db.metadata)
                                        if os.environ.get("HELPCHAIN_TEST_DEBUG") == "1":
                                            print(
                                                f"[TEST DEBUG] moved table {_tbl.name} from module={getattr(_mod,'__name__',None)} into canonical metadata"
                                            )
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass

            if engine is not None:
                _db.metadata.create_all(bind=engine)
            else:
                # last-resort: let Flask-SQLAlchemy create on its default
                _db.create_all()

            # Ensure SQLAlchemy registers the engine for the Flask app so
            # request-time code (which may lazily obtain binds) uses the same
            # engine we just created tables on. This helps avoid cases where
            # modules imported earlier hold a reference to an engine bound to
            # the instance DB path.
            try:
                from backend import appy as _appy_mod

                if hasattr(_appy_mod, "_ensure_db_engine_registration"):
                    _appy_mod._ensure_db_engine_registration()
            except Exception:
                # Non-fatal: continue even if registration helper isn't present
                pass
            # Reinitialize analytics_service (and similar subsystems) that may
            # have been initialized earlier with a session bound to the old
            # engine. Rebinding them ensures they use the test DB session.
            try:
                from backend import analytics_service as _analytics_mod
                from backend.extensions import db as _db

                if hasattr(_analytics_mod, "init_analytics_service"):
                    _analytics_mod.init_analytics_service(_db.session)
            except Exception:
                # Non-fatal: analytics reinit is a best-effort to remove stale
                # session/engine references created at import time.
                pass

            # Attempt application-level seeding (create default admin user)
            # Some app code provides a _seed_once helper that creates a default
            # admin; call it here if available so tests relying on a seeded
            # admin user start reliably.
            try:
                seed = getattr(_appy, "_seed_once", None)
                if callable(seed):
                    seed()
            except Exception:
                # Non-fatal; tests will create admin explicitly if necessary
                pass

            # If the app-level seeding did not populate an admin user (this can
            # happen when different SQLAlchemy instances/engines are in play
            # during test startup), create a default admin directly using the
            # canonical backend.extensions.db session so request-time code can
            # see it.
            try:
                from backend.extensions import db as _db

                try:
                    from backend.models import AdminUser, User, RoleEnum

                    # Use transactional begin to ensure commit and release of connection
                    with _db.session.begin():
                        existing = (
                            _db.session.query(AdminUser)
                            .filter_by(username="admin")
                            .first()
                        )
                        if not existing:
                            admin_user = AdminUser(
                                username="admin",
                                email="admin@helpchain.live",
                            )
                            # Use test-friendly default password if not configured
                            admin_user.set_password(
                                os.getenv("ADMIN_USER_PASSWORD", "Admin123")
                            )
                            _db.session.add(admin_user)
                            _db.session.flush()

                            # Ensure User record exists for permissions
                            existing_user = (
                                _db.session.query(User)
                                .filter_by(username="admin")
                                .first()
                            )
                            if not existing_user:
                                user = User(
                                    username="admin",
                                    email="admin@helpchain.live",
                                    password_hash=admin_user.password_hash,
                                    role=RoleEnum.superadmin,
                                    is_active=True,
                                )
                                _db.session.add(user)
                except Exception:
                    # If models or extensions aren't importable, skip gracefully
                    pass
            except Exception:
                pass

            meta_tables_after = list(getattr(_db, "metadata", {}).tables.keys())
            print(
                "[TEST DEBUG] SQLAlchemy metadata tables after create_all:",
                meta_tables_after,
            )
        except Exception as _e:
            print("[TEST DEBUG] diagnostics/create_all failed:", _e)

        try:
            yield
        finally:
            try:
                # Drop using the same engine if available to clean up the file DB
                try:
                    engine = _db.get_engine(_appy)
                except Exception:
                    engine = getattr(_db, "engine", None)

                if engine is not None:
                    _db.metadata.drop_all(bind=engine)
                else:
                    _db.drop_all()
            except Exception:
                pass


@pytest.fixture
def set_pending_admin_session(client):
    """Helper fixture to set a pending admin 2FA session for tests.

    Returns a callable that sets session keys and returns a small dict with
    the admin_id and code so tests can assert helper effects.
    """

    def _set(*args, code: str = "123456", expires_seconds: int = 300):
        # Accept either (client, code=..., expires_seconds=...) or (code=..., expires_seconds=...)
        admin_id = None
        local_client = client
        if args:
            # If first arg looks like a FlaskClient, use it
            maybe_client = args[0]
            if hasattr(maybe_client, "session_transaction"):
                local_client = maybe_client
        try:
            from backend.extensions import db as _db

            try:
                from backend.models import AdminUser
            except Exception:
                AdminUser = None

            if AdminUser is not None:
                admin_obj = (
                    _db.session.query(AdminUser).filter_by(username="admin").first()
                )
                if admin_obj:
                    admin_id = getattr(admin_obj, "id", None)
        except Exception:
            admin_id = None

        with local_client.session_transaction() as session:
            session["pending_admin_id"] = admin_id
            session["pending_email_2fa"] = True
            session["email_2fa_code"] = code
            session["email_2fa_expires"] = (
                datetime.now() + timedelta(seconds=expires_seconds)
            ).timestamp()

        return {"admin_id": admin_id, "code": code}

    return _set
