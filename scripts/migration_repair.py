from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db

DATABASE_URL = None


def get_db_schema(engine):
    inspector = inspect(engine)
    schema = {}

    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        schema[table] = {c["name"]: str(c["type"]) for c in columns}

    return schema


def get_model_schema():
    schema = {}

    for table in db.metadata.tables.values():
        schema[table.name] = {
            column.name: str(column.type)
            for column in table.columns
        }

    return schema


def compare(db_schema, model_schema):

    fixes = []

    for table, columns in model_schema.items():

        if table not in db_schema:
            fixes.append(("create_table", table))
            continue

        db_cols = db_schema[table]

        for col, typ in columns.items():

            if col not in db_cols:
                fixes.append(("add_column", table, col, typ))

            elif db_cols[col] != typ:
                fixes.append(("type_mismatch", table, col, typ))

    return fixes


def generate_safe_migration(fixes):

    lines = []

    for fix in fixes:

        if fix[0] == "add_column":
            table, col, typ = fix[1], fix[2], fix[3]

            lines.append(
                f'op.add_column("{table}", sa.Column("{col}", sa.{typ}(), nullable=True))'
            )

    return "\n".join(lines)


def main():
    app = create_app()
    with app.app_context():
        db_url = str(db.engine.url)

    engine = create_engine(db_url)

    db_schema = get_db_schema(engine)
    with app.app_context():
        model_schema = get_model_schema()

    fixes = compare(db_schema, model_schema)

    if not fixes:
        print("✔ schema in sync")
        return

    print("\nDetected schema drift:\n")

    for f in fixes:
        print(f)

    print("\nSuggested SAFE migration:\n")

    print(generate_safe_migration(fixes))


if __name__ == "__main__":
    main()
