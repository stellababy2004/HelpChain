import logging

from sqlalchemy import inspect

from backend.extensions import db
from backend.models import Structure

log = logging.getLogger("helpchain.guard")


def ensure_default_structure() -> dict:
    """
    Auto-healing guard for tenant bootstrap.

    Behavior:
    - If 'structures' table is missing: log error, do not mutate schema.
    - If table exists but default tenant is missing: create it.
    - If everything is OK: no-op.

    Returns a small structured status dict for logs/admin usage.
    """
    result = {
        "database": "ok",
        "structures_table": "ok",
        "default_structure": "ok",
        "action": "none",
    }

    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        if "structures" not in tables:
            result["structures_table"] = "missing"
            result["action"] = "manual_migration_required"
            log.error(
                "DB guard: 'structures' table is missing. Run migrations: flask db upgrade"
            )
            return result

        default_structure = Structure.query.filter_by(slug="default").first()
        if default_structure:
            log.info("DB guard: default structure already present (slug='default').")
            return result

        bootstrap = Structure(name="Default", slug="default")
        db.session.add(bootstrap)
        db.session.commit()

        result["default_structure"] = "created"
        result["action"] = "default_structure_seeded"
        log.warning("DB guard: default structure was missing and has been auto-created.")

    except Exception as exc:
        db.session.rollback()
        result["database"] = "error"
        result["action"] = "rollback"
        log.exception("DB guard failed: %s", exc)

    return result
