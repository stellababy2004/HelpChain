import os
import sys

from flask import Flask

# Ensure repository root is on sys.path so `backend` package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import importlib.util

# Load `backend/extensions.py` directly to avoid executing `backend.__init__`
# (which imports `backend.models` too early). This mirrors how tests import
# models after the Flask app has been initialized.
spec = importlib.util.spec_from_file_location(
    "backend_extensions",
    os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        "backend",
        "extensions.py",
    ),
)
_ext_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_ext_mod)
_db = _ext_mod.db

app = Flask("tmp")
app.config.update(
    TESTING=True,
    SECRET_KEY="test-secret",
    SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
_db.init_app(app)

with app.app_context():
    # Create tables on the Flask-SQLAlchemy engine before importing
    # models so modules that attempt to sync metadata find the engine.
    _db.create_all()

    # Import models after the Flask `db` is initialized to mirror test fixture order
    from backend.models import Permission, PermissionEnum, Role, RolePermission

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

    admin_role = _db.session.query(Role).filter_by(name="Администратор").first()
    if not admin_role:
        admin_role = Role(
            name="Администратор", description="Администратор", is_system_role=True
        )
        _db.session.add(admin_role)
        try:
            _db.session.flush()
        except Exception:
            pass

    for codename, perm in created.items():
        exists = (
            _db.session.query(RolePermission)
            .filter_by(role_id=admin_role.id, permission=perm.codename)
            .first()
        )
        print("exists check for", codename, "->", exists)
        if not exists:
            try:
                rp = RolePermission(role=admin_role, permission=perm.codename)
            except Exception as e:
                print("assignment via role object failed:", e)
                try:
                    rp = RolePermission(role_id=admin_role.id, permission=perm.codename)
                except Exception as e2:
                    print("assignment via ids failed:", e2)
                    continue
            _db.session.add(rp)

    try:
        _db.session.commit()
    except Exception as e:
        print("commit failed:", e)
        try:
            _db.session.rollback()
        except Exception:
            pass

    print("Permissions:", [(p.id, p.codename) for p in Permission.query.all()])
    print("Roles:", [(r.id, r.name) for r in Role.query.all()])
    print("RolePermissions raw query:", _db.session.query(RolePermission).all())
    for rp in _db.session.query(RolePermission).all():
        print(
            "RP:",
            getattr(rp, "id", None),
            "role_id",
            getattr(rp, "role_id", None),
            "permission_id",
            getattr(rp, "permission_id", None),
            "permission_rel",
            getattr(rp, "permission", None),
        )

print("done")
