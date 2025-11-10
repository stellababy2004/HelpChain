import pytest

# Simple local conftest for tests folder to provide the `app` fixture used by
# pytest-flask. This keeps fixture discovery close to the tests and avoids
# surprises with conftest resolution order.

import os
import pathlib
import pytest

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
            if engine is not None:
                _db.metadata.create_all(bind=engine)
            else:
                # last-resort: let Flask-SQLAlchemy create on its default
                _db.create_all()

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
