import sys


def _is_sqlalchemy_like(obj):
    # Heuristic: Flask-SQLAlchemy exposes `init_app` and a `session` proxy.
    try:
        return obj is not None and hasattr(obj, "init_app")
    except Exception:
        return False


def test_single_sqlalchemy_instance():
    """Ensure the repository exposes only a single Flask-SQLAlchemy `db` object.

    This test collects `db` attributes from loaded modules and asserts that
    all found SQLAlchemy-like objects resolve to the same instance (by id).
    It is designed as a fast-fail CI check so accidental additional
    `SQLAlchemy()` instantiations are detected early.
    """
    ids = set()
    locations = {}

    # Collect candidate `db` objects from imported modules
    for mod in list(sys.modules.values()):
        try:
            db = getattr(mod, "db", None)
            if _is_sqlalchemy_like(db):
                ids.add(id(db))
                locations[id(db)] = locations.get(id(db), []) + [
                    getattr(mod, "__name__", str(mod))
                ]
        except Exception:
            pass

    # Also try to import the canonical extension and include it
    try:
        from backend.extensions import db as canonical_db

        ids.add(id(canonical_db))
        locations[id(canonical_db)] = locations.get(id(canonical_db), []) + [
            "backend.extensions"
        ]
    except Exception:
        # If importing backend.extensions fails, still assert on what we found
        pass

    assert len(ids) <= 1, f"Multiple SQLAlchemy() instances detected: {locations}"
