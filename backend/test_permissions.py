import pytest
from flask import Flask, session
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.models import PermissionEnum, Role, User, UserRole
from permissions import (
    get_user_permissions,
    get_user_roles,
    has_permission,
    initialize_default_roles_and_permissions,
)


@pytest.fixture
def permissions_app():
    app = Flask("permissions_test")
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        initialize_default_roles_and_permissions()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user_id(permissions_app):
    with permissions_app.app_context():
        admin_role = Role.query.filter_by(name="Администратор").first()
        assert admin_role is not None, "Expected default admin role to exist"

        user = User(
            username="testadmin",
            email="testadmin@example.com",
            password_hash=generate_password_hash("password123"),
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db.session.commit()

        return user.id


@pytest.fixture
def regular_user_id(permissions_app):
    with permissions_app.app_context():
        user = User(
            username="regularuser",
            email="regular@example.com",
            password_hash=generate_password_hash("password123"),
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def _collect_permission_codes(role):
    return {
        getattr(role_perm.permission.codename, "value", role_perm.permission.codename)
        for role_perm in role.role_permissions
    }


def test_admin_role_initialized_with_core_permissions(permissions_app):
    with permissions_app.app_context():
        admin_role = Role.query.filter_by(name="Администратор").first()
        assert admin_role is not None

        permission_codes = _collect_permission_codes(admin_role)
        assert PermissionEnum.ADMIN_ACCESS.value in permission_codes
        assert PermissionEnum.MANAGE_USERS.value in permission_codes


def test_has_permission_requires_logged_in_user(permissions_app):
    with permissions_app.test_request_context():
        assert not has_permission(PermissionEnum.ADMIN_ACCESS.value)


def test_has_permission_returns_true_for_admin(permissions_app, admin_user_id):
    with permissions_app.test_request_context():
        session["user_id"] = admin_user_id
        assert has_permission(PermissionEnum.ADMIN_ACCESS.value)
        assert has_permission(PermissionEnum.MANAGE_USERS.value)
        assert not has_permission("nonexistent_permission")


def test_has_permission_returns_false_for_regular_user(
    permissions_app, regular_user_id
):
    with permissions_app.test_request_context():
        session["user_id"] = regular_user_id
        assert not has_permission(PermissionEnum.ADMIN_ACCESS.value)


def test_get_user_permissions_reflects_role_assignments(permissions_app, admin_user_id):
    with permissions_app.app_context():
        permission_list = set(get_user_permissions(admin_user_id))

    assert PermissionEnum.ADMIN_ACCESS.value in permission_list
    assert PermissionEnum.MANAGE_USERS.value in permission_list


def test_get_user_roles_returns_human_readable_names(permissions_app, admin_user_id):
    with permissions_app.app_context():
        roles = get_user_roles(admin_user_id)

    assert "Администратор" in roles
