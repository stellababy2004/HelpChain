"""
Root-level pytest configuration and database setup for backend tests.

This ensures that tests placed directly under `backend/` (not
`backend/tests/`) initialize a consistent SQLite schema before any test
code queries tables such as `admin_users`.
"""

import os
import pathlib

import pytest

# 1) Ensure a file-backed SQLite URI is available early so the Flask app
#    binds its engine to a persistent test DB file (shared across connections).
if not os.environ.get("DATABASE_URL"):
    test_db_path = pathlib.Path(__file__).with_name("test_local.sqlite")
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"

# Mark we are running tests to activate test-specific paths in the app
os.environ.setdefault("HELPCHAIN_TESTING", "1")


def _ensure_app_uses_test_uri(app_obj):
    """Force the Flask app to use the DATABASE_URL from the environment."""
    try:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            app_obj.config["SQLALCHEMY_DATABASE_URI"] = db_url
            # Also register the test file path for helpers that consult it
            if db_url.startswith("sqlite///"):
                app_obj.config.setdefault(
                    "_TEST_DB_PATH", db_url.replace("sqlite:///", "")
                )
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    """Create all tables once per test session and drop them at the end.

    We import the Flask app and extensions lazily and perform create_all()
    inside an application context to guarantee all mapped tables exist.
    """
    from backend.appy import app as _appy
    from backend.extensions import db as _db

    _ensure_app_uses_test_uri(_appy)

    with _appy.app_context():
        # Create schema on the exact engine bound to the Flask app
        try:
            engine = getattr(_db, "engine", None)
            if engine is not None:
                _db.metadata.create_all(bind=engine)
            else:
                _db.create_all()
        except Exception as e:
            print("[TEST DEBUG] root prepare_database create_all failed:", e)

        # Best-effort: seed default admin if missing so admin-related
        # tests don't fail on empty databases.
        try:
            from backend.models import AdminUser, RoleEnum, User

            with _db.session.begin():
                if not _db.session.query(AdminUser).filter_by(username="admin").first():
                    admin = AdminUser(username="admin", email="admin@helpchain.live")
                    admin.set_password(os.getenv("ADMIN_USER_PASSWORD", "Admin123"))
                    _db.session.add(admin)
                    if not _db.session.query(User).filter_by(username="admin").first():
                        user = User(
                            username="admin",
                            email="admin@helpchain.live",
                            password_hash=admin.password_hash,
                            role=RoleEnum.superadmin,
                            is_active=True,
                        )
                        _db.session.add(user)
        except Exception:
            pass

    # Run tests
    try:
        yield
    finally:
        # Drop schema to leave a clean workspace
        with _appy.app_context():
            try:
                engine = getattr(_db, "engine", None)
                if engine is not None:
                    _db.metadata.drop_all(bind=engine)
                else:
                    _db.drop_all()
            except Exception:
                pass


@pytest.fixture
def app():
    """Expose the Flask app object for pytest-flask fixtures like `client`."""
    from backend.appy import app as _appy

    _ensure_app_uses_test_uri(_appy)
    return _appy
