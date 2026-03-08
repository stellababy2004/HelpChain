import os
import pathlib
import tempfile
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command
from flask import Flask

try:
    # canonical db instance used by the app
    from backend.extensions import db as canonical_db
except Exception:
    canonical_db = None

try:
    from flask_migrate import Migrate
except Exception:
    Migrate = None


def test_alembic_upgrade_on_clean_sqlite(tmp_path):
    """Integration test: apply Alembic migrations to a fresh SQLite file DB.

    This test creates a temporary SQLite database file, configures Alembic to
    use it, runs `upgrade head` and asserts that at least some expected
    tables were created. This helps catch migration ordering or runtime
    errors in CI early.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]

    # Canonical Alembic root is repository-level migrations/
    alembic_ini = repo_root / "migrations" / "alembic.ini"
    assert alembic_ini.exists(), f"alembic.ini not found at {alembic_ini}"

    db_file = tmp_path / "alembic_test.db"
    db_url = f"sqlite:///{db_file}"

    cfg = Config(str(alembic_ini))
    # Force the SQLAlchemy url to our temporary DB
    cfg.set_main_option("sqlalchemy.url", db_url)
    # Ensure Alembic uses the canonical repository migrations folder
    cfg.set_main_option("script_location", str(repo_root / "migrations"))

    # Run the migrations. Alembic's env.py expects a Flask `current_app` with
    # the Flask-Migrate extension registered. Create a minimal app context
    # and register the canonical `db` and `Migrate` so env.py can obtain the
    # engine and metadata.
    if canonical_db is None or Migrate is None:
        raise RuntimeError(
            "Required Flask extensions (backend.extensions or flask_migrate) not importable"
        )

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    # Ensure SQLite can be used from multiple connections in tests
    app.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS", {"connect_args": {"check_same_thread": False}}
    )

    # Initialize extensions and Flask-Migrate
    canonical_db.init_app(app)
    migrate = Migrate(app, canonical_db)

    # Run alembic upgrade within the app context so env.py can reference current_app
    with app.app_context():
        command.upgrade(cfg, "head")

    # Verify that tables were created
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Expect at least these core tables to be present after applying migrations
    assert len(tables) > 0, "No tables created by Alembic migrations"
    assert (
        ("volunteers" in tables) or ("users" in tables) or ("admin_users" in tables)
    ), f"Expected core tables not found in {tables}"
