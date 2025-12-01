import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine():
    try:
        # Prefer the explicit `.engine` attribute available on newer
        # Flask-SQLAlchemy versions to avoid deprecation warnings. Use
        # the project's helper which centralizes compatibility logic.
        target_db = current_app.extensions["migrate"].db
        try:
            from backend.extensions import get_db_engine

            eng = get_db_engine(current_app, target_db)
            if eng is not None:
                return eng
        except Exception:
            # Fall back to older accessors if the helper isn't importable
            eng = getattr(target_db, "engine", None)
            if eng is not None:
                return eng
            if hasattr(target_db, "get_engine"):
                try:
                    return target_db.get_engine(current_app)
                except Exception:
                    return None
        return eng
    except Exception:
        # If anything goes wrong, raise so alembic can fall back to INI URL
        raise


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# Prefer an existing sqlalchemy.url from the INI if present. Otherwise try
# to derive it from the Flask application. If a Flask app isn't available
# (for example when running migrations from CI without creating the app),
# avoid raising here so the script can fall back to creating an Engine
# from the INI-provided URL.
try:
    existing_url = config.get_main_option("sqlalchemy.url")
except Exception:
    existing_url = None

if not existing_url:
    try:
        config.set_main_option("sqlalchemy.url", get_engine_url())
    except Exception:
        # current_app isn't available; leave sqlalchemy.url unset so
        # run_migrations_online can create an Engine from the INI URL.
        pass

try:
    target_db = current_app.extensions["migrate"].db
except Exception:
    target_db = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if target_db is None:
        return None
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


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
    context.configure(url=url, target_metadata=get_metadata(), literal_binds=True)

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

    if target_db is not None:
        conf_args = current_app.extensions["migrate"].configure_args
        if conf_args.get("process_revision_directives") is None:
            conf_args["process_revision_directives"] = process_revision_directives

        connectable = get_engine()
    else:
        # No Flask app available; create an Engine from the INI-provided URL.
        from sqlalchemy import engine_from_config, pool

        conf_args = {}
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=get_metadata(), **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
