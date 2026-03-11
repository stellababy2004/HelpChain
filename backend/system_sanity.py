import logging
from datetime import datetime, timezone

from sqlalchemy import inspect, text

from backend.extensions import db
from backend.models import Structure

log = logging.getLogger("helpchain.sanity")


def run_system_checks():
    checks = {}
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["alembic"] = "ok" if version else "warning"
    except Exception:
        checks["alembic"] = "error"

    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        checks["structures_table"] = "ok" if "structures" in tables else "error"
    except Exception:
        checks["structures_table"] = "error"

    try:
        s = Structure.query.filter_by(slug="default").first()
        checks["default_structure"] = "ok" if s else "warning"
    except Exception:
        checks["default_structure"] = "error"

    checks["timestamp"] = datetime.now(timezone.utc)

    return checks
