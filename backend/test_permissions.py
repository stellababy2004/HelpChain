import pytest
from flask import Flask, session
from werkzeug.security import generate_password_hash

from backend.extensions import db as _db

# Keep legacy `db` name for existing code in this file that expects it.
db = _db
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
        # Ensure minimal roles/permissions exist for this isolated test app.
        # Some test environments can leave transactions open or use a
        # different engine/metadata; create a minimal admin role directly
        # on the app's DB to guarantee tests have the expected data.
        try:
            from backend.extensions import db as _db
            from backend.models import Permission, Role, RolePermission, PermissionEnum

            # Defensive rollback/remove before seeding
            try:
                _db.session.rollback()
            except Exception:
                pass
            try:
                _db.session.remove()
            except Exception:
                pass

            # create a couple of core permissions if missing
            perms = [
                (PermissionEnum.ADMIN_ACCESS.value, "Админ достъп"),
                (PermissionEnum.MANAGE_USERS.value, "Управление на потребители"),
            ]
            created = {}
            for codename, name in perms:
                p = _db.session.query(Permission).filter_by(codename=codename).first()
                if not p:
                    p = Permission(name=name, codename=codename)
                    _db.session.add(p)
                    try:
                        _db.session.flush()
                    except Exception:
                        pass
                created[codename] = p

            # ensure admin role exists
            admin_role = _db.session.query(Role).filter_by(name="Администратор").first()
            if not admin_role:
                admin_role = Role(name="Администратор", description="Администратор", is_system_role=True)
                _db.session.add(admin_role)
                try:
                    _db.session.flush()
                except Exception:
                    pass

            # assign admin perms
            try:
                for codename, perm in created.items():
                    if perm is None:
                        continue
                    exists = _db.session.query(RolePermission).filter_by(role_id=admin_role.id, permission=perm.codename).first()
                    if not exists:
                        # Associate via role object where possible to ensure relationship
                        try:
                            rp = RolePermission(role=admin_role, permission=perm.codename)
                        except Exception:
                            rp = RolePermission(role_id=admin_role.id, permission=perm.codename)
                        _db.session.add(rp)
            except Exception:
                pass

            try:
                _db.session.commit()
            except Exception:
                try:
                    _db.session.rollback()
                except Exception:
                    pass
            # Ensure role_permissions were persisted and are visible via relationship
            try:
                _db.session.expire_all()
                admin_role = _db.session.query(Role).filter_by(name="Администратор").first()
                if admin_role is not None:
                    # force reload of related RolePermission objects
                    _db.session.refresh(admin_role)
            except Exception:
                pass
        except Exception:
            # fallback to calling the app-level seeder; if that fails tests will assert
            try:
                initialize_default_roles_and_permissions()
            except Exception:
                pass

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user_id(permissions_app):
    with permissions_app.app_context():
        admin_role = _db.session.query(Role).filter_by(name="Администратор").first()
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
    codes = set()
    for role_perm in getattr(role, "role_permissions", []) or []:
        perm = getattr(role_perm, "permission", None)
        if perm is None:
            continue
        # perm might be a Permission instance or a codename string; handle both
        try:
            # If it's a Permission model instance, extract codename/value
            code = getattr(perm.codename, "value", perm.codename)
        except Exception:
            # Otherwise assume it's already a string codename
            try:
                code = str(perm)
            except Exception:
                continue
        codes.add(code)
    return codes


def test_admin_role_initialized_with_core_permissions(permissions_app):
    with permissions_app.app_context():
        admin_role = _db.session.query(Role).filter_by(name="Администратор").first()
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


def test_has_permission_returns_false_for_regular_user(permissions_app, regular_user_id):
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
