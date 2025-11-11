import importlib


def _get_db_id(mod_name):
    try:
        mod = importlib.import_module(mod_name)
        m = getattr(mod, "db", None)
        return id(m), getattr(mod, "__file__", None)
    except Exception:
        return None, None


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
    resolved = {}
    for name in candidates:
        db_id, mfile = _get_db_id(name)
        resolved[name] = (db_id, mfile)
        if db_id is not None:
            ids.add(db_id)
    # Print diagnostic mapping to help debug import aliasing in CI/test runs
    print("DB id mapping:")
    for k, (v, mf) in resolved.items():
        print(f"  {k}: id={v} file={mf}")
    # There should be at most one distinct non-None db id
    assert len(ids) <= 1, f"Multiple SQLAlchemy instances detected: {ids}"
