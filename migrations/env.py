import logging
import os
from logging.config import fileConfig

from alembic import context
from flask import current_app

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError, RuntimeError):
        # this works with Flask-SQLAlchemy>=3 or when no app context
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    # First try to get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url.replace("%", "%%")

    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except (AttributeError, RuntimeError):
        return str(get_engine().url).replace("%", "%%")


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option("sqlalchemy.url", get_engine_url())

# Try to get target_db from Flask app, but handle case where no app context exists
try:
    target_db = current_app.extensions["migrate"].db
except RuntimeError:
    # No app context, we'll handle this in the migration functions
    target_db = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if target_db and hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    elif target_db:
        return target_db.metadata
    else:
        # Import metadata directly when no app context
        import os
        import sys

        # Add current directory to path for imports
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        # Ensure all ORM models are imported so metadata is complete.
        from backend.helpchain_backend.src import models  # noqa: F401
        from backend.models import db

        return db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    connectable = None
    conf_args = {}

    if target_db:
        # We have app context, use Flask-Migrate configuration
        conf_args = current_app.extensions["migrate"].configure_args
        if conf_args.get("process_revision_directives") is None:
            conf_args["process_revision_directives"] = process_revision_directives
        connectable = get_engine()
    else:
        # No app context, create engine directly from DATABASE_URL or default to absolute instance/app.db
        from sqlalchemy import create_engine

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        default_sqlite = f"sqlite:///{os.path.join(project_root, 'instance', 'app.db')}"
        database_url = os.getenv("DATABASE_URL", default_sqlite)
        connectable = create_engine(database_url)

    with connectable.connect() as connection:
        if "render_as_batch" not in conf_args:
            conf_args["render_as_batch"] = True
        if "compare_type" not in conf_args:
            conf_args["compare_type"] = True
        if "compare_server_default" not in conf_args:
            conf_args["compare_server_default"] = True
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
