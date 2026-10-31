from __future__ import annotations

from logging.config import fileConfig
import os

from alembic import context
from flask import current_app
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass


def _get_db():
    ext = getattr(current_app, "extensions", {}).get("migrate")
    if ext is not None and hasattr(ext, "db"):
        return ext.db

    from backend.extensions import db

    return db


def get_metadata():
    # Ensure model tables are registered before returning metadata.
    try:
        import backend.models  # noqa: F401
        import backend.models_with_analytics  # noqa: F401
    except Exception:
        pass
    return _get_db().metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db = _get_db()
    connectable = None
    try:
        connectable = db.engine
    except Exception:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        metadata = get_metadata()
        # Do not create application tables implicitly during Alembic runs.
        # Legacy/local callers may opt in explicitly, but strict migration
        # tests and production deployments must rely on migration history.
        allow_metadata_bootstrap = os.getenv(
            "ALEMBIC_ALLOW_METADATA_CREATE_ALL", ""
        ).strip().lower() in {"1", "true", "yes"}
        if allow_metadata_bootstrap:
            metadata.create_all(bind=connection)
        context.configure(
            connection=connection,
            target_metadata=metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
