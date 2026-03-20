from __future__ import annotations

import pathlib
import sys
from typing import Dict

from sqlalchemy import inspect, text

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import AdminUser


def _alembic_head() -> str | None:
    cfg_path = ROOT / "migrations" / "alembic.ini"
    if not cfg_path.exists():
        return None
    cfg = Config(str(cfg_path))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    return heads[0] if heads else None


def _db_revision() -> str | None:
    try:
        return db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return None


def _check_routes(app) -> Dict[str, bool]:
    rules = {r.rule for r in app.url_map.iter_rules()}
    return {
        "/admin": "/admin" in rules or "/admin/" in rules,
        "/admin/login": "/admin/login" in rules,
        "/admin/ops/login": "/admin/ops/login" in rules,
        "/admin/requests": "/admin/requests" in rules,
        "/admin/command": "/admin/command" in rules,
    }


def _check_tables() -> Dict[str, bool]:
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
    app = create_app()
    with app.app_context():
        db_ok = True
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        table_status = _check_tables() if db_ok else {}
        admin_count = AdminUser.query.count() if table_status.get("admin_users") else 0
        route_status = _check_routes(app)

        head = _alembic_head()
        current = _db_revision()
        mig_ok = bool(head and current and head == current)

        tables_ok = all(table_status.values()) if table_status else False
        routes_ok = all(route_status.values())
        admin_ok = admin_count > 0

        print("SYSTEM HEALTH CHECK")
        print(f"Database connection: {'OK' if db_ok else 'MISSING'}")
        print(f"Tables: {'OK' if tables_ok else 'MISSING'}")
        print(f"Admin user: {'OK' if admin_ok else 'MISSING'}")
        print(f"Routes: {'OK' if routes_ok else 'MISSING'}")
        print(f"Migrations: {'OK' if mig_ok else 'MISSING'}")
        print("System ready." if all([db_ok, tables_ok, admin_ok, routes_ok, mig_ok]) else "System needs attention.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
