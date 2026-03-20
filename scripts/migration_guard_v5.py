from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, Date, DateTime, Float, Integer


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations" / "versions"
ALEMBIC_INI = ROOT / "migrations" / "alembic.ini"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXES: list[str] = []


def get_database_url() -> str:
    from backend.helpchain_backend.src.config import Config

    return Config.SQLALCHEMY_DATABASE_URI


def get_db_schema():
    engine = create_engine(get_database_url())
    inspector = inspect(engine)

    schema = {}

    for table in inspector.get_table_names():
        columns = {col["name"]: col for col in inspector.get_columns(table)}
        indexes = {
            idx["name"]
            for idx in inspector.get_indexes(table)
            if idx.get("name") and not idx["name"].startswith("sqlite_autoindex")
        }

        schema[table] = {
            "columns": columns,
            "indexes": indexes,
        }

    engine.dispose()
    return schema


def get_models_metadata():
    import backend.models  # noqa: F401
    from backend.extensions import db

    return db.metadata


def map_type(col) -> str:
    t = col.type

    if isinstance(t, Integer):
        return "sa.Integer()"
    if isinstance(t, BigInteger):
        return "sa.BigInteger()"
    if isinstance(t, Float):
        return "sa.Float()"
    if isinstance(t, Boolean):
        return "sa.Boolean()"
    if isinstance(t, DateTime):
        return "sa.DateTime()"
    if isinstance(t, Date):
        return "sa.Date()"

    type_name = t.__class__.__name__

    if hasattr(t, "length") and getattr(t, "length", None):
        return f"sa.{type_name}(length={t.length})"

    return f"sa.{type_name}()"


def detect_and_fix(db_schema, metadata) -> None:
    for table in metadata.tables.values():
        table_name = table.name

        if table_name not in db_schema:
            continue

        db_cols = db_schema[table_name]["columns"]
        db_indexes = db_schema[table_name]["indexes"]

        for col in table.columns:
            if col.name in db_cols or col.primary_key:
                continue

            # Auto-fix remains additive and nullable for safety.
            FIXES.append(
                f'op.add_column("{table_name}", sa.Column("{col.name}", {map_type(col)}, nullable=True))'
            )

        for idx in table.indexes:
            if not idx.name or idx.name in db_indexes:
                continue

            cols = [column.name for column in idx.columns]
            FIXES.append(
                f'op.create_index("{idx.name}", "{table_name}", {cols!r}, unique={bool(idx.unique)})'
            )


def get_single_head() -> str:
    if not ALEMBIC_INI.exists():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")

    config = AlembicConfig(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    heads = list(script.get_heads())

    if not heads:
        raise RuntimeError("No Alembic heads found")
    if len(heads) > 1:
        raise RuntimeError(f"Multiple heads detected: {heads}")

    return heads[0]


def generate_migration() -> None:
    if not FIXES:
        print("No fixes needed.")
        return

    revision = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    down_revision = get_single_head()
    filename = MIGRATIONS_DIR / f"{revision}_auto_fix.py"

    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    code = f'''"""
auto fix migration

Revision ID: {revision}
Revises: {down_revision}
Create Date: {created_at}
"""

from alembic import op
import sqlalchemy as sa


revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade():
'''

    for fix in FIXES:
        code += f"    {fix}\n"

    code += """


def downgrade():
    pass
"""

    filename.write_text(code, encoding="utf-8")
    print(f"Generated migration: {filename}")


def main() -> None:
    if not MIGRATIONS_DIR.exists():
        print("No migrations directory found.")
        sys.exit(0)

    db_schema = get_db_schema()
    metadata = get_models_metadata()

    detect_and_fix(db_schema, metadata)
    generate_migration()


if __name__ == "__main__":
    main()
