import pytest


def test_achievements_table_present(app):
    """Regression test: ensure the 'achievements' table is present in metadata.

    This guards against regressions where models are imported against a
    different SQLAlchemy instance or omitted from metadata before
    `db.create_all()` in tests.
    """
    try:
        from appy import db
    except Exception:
        try:
            # fallback to known alias
            from extensions import db  # type: ignore
        except Exception:
            from helpchain_backend.src.extensions import db as db  # type: ignore

    with app.app_context():
        tables = set(db.metadata.tables.keys())
        assert (
            "achievements" in tables
        ), f"achievements not in metadata: {sorted(tables)}"
