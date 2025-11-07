import importlib


def _get_db_id(mod_name):
    try:
        mod = importlib.import_module(mod_name)
        return id(getattr(mod, "db", None))
    except Exception:
        return None


def test_single_sqlalchemy_instance():
    """Ensure all common extension import names reference the same SQLAlchemy db.

    This prevents regressions where a shim or alternate import path creates a
    second SQLAlchemy() instance and model classes register against different
    metadata registries.
    """
    candidates = [
        "backend.extensions",
        "extensions",
        "helpchain_backend.src.extensions",
        "appy",
        "models",
    ]
    ids = set()
    for name in candidates:
        db_id = _get_db_id(name)
        if db_id is not None:
            ids.add(db_id)
    # There should be at most one distinct non-None db id
    assert len(ids) <= 1, f"Multiple SQLAlchemy instances detected: {ids}"
