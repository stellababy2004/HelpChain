from __future__ import annotations

import os
import pathlib
import sys

from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "backend" / "instance" / "app.db"

DELETE_FILES = [
    DB_PATH,
]


def _delete_if_exists(path: pathlib.Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _delete_globs() -> None:
    for path in (ROOT / "backend" / "instance").glob("*.db"):
        if path == DB_PATH:
            continue
        _delete_if_exists(path)
    for pattern in ("*.sqlite", "*.sqlite3"):
        for path in ROOT.glob(pattern):
            _delete_if_exists(path)
        for path in (ROOT / "backend").glob(pattern):
            _delete_if_exists(path)
        for path in (ROOT / "backend" / "instance").glob(pattern):
            _delete_if_exists(path)


def _ensure_instance_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _set_db_env() -> None:
    db_url = f"sqlite:///{DB_PATH.as_posix()}"
    os.environ["DATABASE_URL"] = db_url
    os.environ["HC_LOCAL_DB"] = db_url


def _run_migrations(app) -> None:
    from flask_migrate import upgrade

    with app.app_context():
        upgrade()


def _ensure_orm_tables(app) -> None:
    from backend.extensions import db

    with app.app_context():
        db.create_all()


def _ensure_admin(app) -> int:
    from backend.extensions import db
    from backend.models import AdminUser, Structure, get_default_structure

    with app.app_context():
        bind = db.session.get_bind()
        inspector = inspect(bind)
        if "admin_users" not in inspector.get_table_names():
            print("Database not initialized. Run migrations.")
            return 0

        structure = get_default_structure()
        if not structure:
            structure = Structure(name="Default", slug="default", status="active")
            db.session.add(structure)
            db.session.commit()

        existing = AdminUser.query.count()
        if existing > 0:
            return existing

        admin = AdminUser(
            username="admin",
            email="admin@localhost",
            role="superadmin",
            is_active=True,
            structure_id=structure.id,
        )
        admin.password_hash = generate_password_hash("943415StoyanovaNova!")
        db.session.add(admin)
        db.session.commit()
        return 1


def _check_routes(app) -> dict[str, bool]:
    rules = {r.rule for r in app.url_map.iter_rules()}
    return {
        "/admin": "/admin" in rules or "/admin/" in rules,
        "/admin/login": "/admin/login" in rules,
        "/admin/ops/login": "/admin/ops/login" in rules,
        "/admin/requests": "/admin/requests" in rules,
    }


def _check_tables(app) -> dict[str, bool]:
    from backend.extensions import db

    with app.app_context():
        inspector = inspect(db.session.get_bind())
        tables = set(inspector.get_table_names())
        return {
            "structures": "structures" in tables,
            "users": "users" in tables,
            "admin_users": "admin_users" in tables,
            "cases": "cases" in tables,
            "case_events": "case_events" in tables,
        }


def main() -> int:
    _set_db_env()
    print("Deleting old databases...")
    for path in DELETE_FILES:
        _delete_if_exists(path)
    _delete_globs()
    _ensure_instance_dir()

    print("Creating database...")
    DB_PATH.touch(exist_ok=True)

    from backend.helpchain_backend.src.app import create_app

    app = create_app()

    print("Running migrations...")
    _run_migrations(app)

    print("Ensuring ORM tables exist...")
    _ensure_orm_tables(app)
    print("Database schema verified.")

    print("Creating admin user...")
    admin_count = _ensure_admin(app)

    print("Dev environment ready.")
    print(f"Database path: {DB_PATH}")
    print(f"Admin user count: {admin_count}")
    print(f"Routes OK: {_check_routes(app)}")
    print(f"Tables OK: {_check_tables(app)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
