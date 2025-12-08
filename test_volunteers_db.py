#!/usr/bin/env python3
"""Pytest-compatible checks for the volunteers table.

This file was previously executing DB queries at import time which caused
pytest collection to fail (OperationalError: no such table). Convert it to a
proper pytest test that uses the `app` fixture so the test DB and schema are
prepared before queries run.
"""

import pytest

from backend.models import Volunteer

# Rely on the repository-level `app` fixture provided by `conftest.py`.
# If pytest is invoked from inside `tests/` the richer `tests.conftest.py`
# fixtures will still be used by pytest's fixture resolution.


def test_volunteers_table_exists(app):
    """Ensure the `volunteers` table exists and can be queried."""
    from backend.extensions import db

    with app.app_context():
        # Ensure tables exist (app fixture attempts this; redundant-but-safe)
        try:
            db.create_all()
        except Exception:
            pass

        # Should not raise; returns integer count
        count = db.session.query(Volunteer).count()
        assert isinstance(count, int)
