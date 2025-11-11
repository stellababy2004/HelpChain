import pytest
from flask import Flask, session
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.models import Permission, PermissionEnum, Role, User, UserRole
from permissions import has_permission, initialize_default_roles_and_permissions


@pytest.fixture
def standalone_app():
    app = Flask("permissions_standalone")
    app.config.update(
        TESTING=True,
        SECRET_KEY="standalone-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Only dispose the engine for file-backed databases. Disposing the
        # engine for an in-memory SQLite database will drop the schema
        # because the in-memory DB is connection-scoped.
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
        if ":memory:" not in uri:
            try:
                db.engine.dispose()
            except Exception:
                pass

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
        # Ensure engine disposes connections so sqlite3.Connection objects
        # aren't left open by the SQLAlchemy engine/pool during tests.
        try:
            db.engine.dispose()
        except Exception:
            # Best-effort; don't fail teardown if dispose isn't available
            pass


@pytest.fixture
def app_with_defaults(standalone_app):
    with standalone_app.app_context():
        initialize_default_roles_and_permissions()
    return standalone_app


@pytest.fixture
def standalone_admin_user_id(app_with_defaults):
    with app_with_defaults.app_context():
        admin_role = Role.query.filter_by(name="Администратор").first()
        assert admin_role is not None, "Expected default admin role to be created"

        user = User(username="standalone_admin", email="standalone@example.com")
        try:
            user.set_password("password123")
        except Exception:
            user.password_hash = generate_password_hash("password123")
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db.session.commit()

        return user.id


def test_initialize_default_roles_is_idempotent(standalone_app):
    with standalone_app.app_context():
        initialize_default_roles_and_permissions()
        initial_role_count = Role.query.count()
        initial_permission_count = Permission.query.count()

        initialize_default_roles_and_permissions()

        assert Role.query.count() == initial_role_count
        assert Permission.query.count() == initial_permission_count


def test_has_permission_with_session_context(
    app_with_defaults, standalone_admin_user_id
):
    with app_with_defaults.test_request_context():
        session["user_id"] = standalone_admin_user_id
        assert has_permission(PermissionEnum.ADMIN_ACCESS.value)
        assert has_permission(PermissionEnum.MANAGE_USERS.value)


def test_has_permission_denies_missing_role(app_with_defaults):
    with app_with_defaults.app_context():
        user = User(username="no_role_user", email="norole@example.com")
        try:
            user.set_password("password123")
        except Exception:
            user.password_hash = generate_password_hash("password123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with app_with_defaults.test_request_context():
        session["user_id"] = user_id
        assert not has_permission(PermissionEnum.ADMIN_ACCESS.value)
