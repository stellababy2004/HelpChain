import logging

from sqlalchemy import inspect

from backend.extensions import db
from backend.models import Structure

log = logging.getLogger("helpchain.startup")


def check_database_integrity():
    """
    Lightweight startup check to detect schema drift or missing bootstrap data.
    Does not modify runtime behavior; only logs warnings.
    """
    try:
        engine = db.engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Check 1: structures table exists
        if "structures" not in tables:
            log.error("DB integrity issue: 'structures' table missing")
            log.error("Run: flask db upgrade")
            return

        # Check 2: default tenant exists
        default_structure = Structure.query.filter_by(slug="default").first()
        if not default_structure:
            log.warning("default tenant missing (slug='default')")
            log.warning("System may fail in tenant resolution")
        else:
            log.info("default tenant found")

    except Exception as e:
        log.exception("Startup DB integrity check failed: %s", e)
