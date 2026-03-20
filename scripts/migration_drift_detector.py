from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import NullType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print(title: str) -> None:
    print(f"\n{title}")


def _type_name(t: Any) -> str:
    try:
        if isinstance(t, type):
            return t.__name__
        if hasattr(t, "__class__"):
            return t.__class__.__name__
    except Exception:
        pass
    return str(t)


def _normalize_type(t: Any) -> str:
    if t is None:
        return ""
    if isinstance(t, NullType):
        return "null"

    name = _type_name(t).lower()

    # Normalize common aliases across SQLAlchemy / SQLite / Postgres
    if name in {"integer", "int", "integer".upper().lower()}:
        return "int"
    if name in {"biginteger", "bigint"}:
        return "bigint"
    if name in {"boolean", "bool"}:
        return "bool"
    if name in {"float", "real", "numeric", "decimal"}:
        return "float"
    if name in {"string", "varchar", "text"}:
        return "string"
    if name in {"datetime", "timestamp", "date", "time"}:
        return "datetime"

    return name


def _severity_counts(events: List[Tuple[str, str]]) -> Dict[str, int]:
    counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
    for sev, _ in events:
        if sev in counts:
            counts[sev] += 1
    return counts


def _index_signature(cols: List[str], unique: bool) -> Tuple[Tuple[str, ...], bool]:
    return (tuple(cols), bool(unique))


def main() -> int:
    try:
        from backend.helpchain_backend.src.app import create_app
        from backend.extensions import db
    except Exception as exc:
        print("FAILED TO IMPORT APP/DB:", exc)
        return 2

    app = create_app()
    events: List[Tuple[str, str]] = []

    with app.app_context():
        metadata = db.metadata
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name

        if dialect == "sqlite":
            events.append(("INFO", "SQLite type normalization applied"))

        model_tables = {t for t in metadata.tables.keys() if t != "alembic_version"}
        db_tables = {
            t
            for t in inspector.get_table_names()
            if t != "alembic_version" and not t.startswith("_alembic_tmp_")
        }

        # Table drift
        missing_tables = sorted(model_tables - db_tables)
        extra_tables = sorted(db_tables - model_tables)
        for t in missing_tables:
            events.append(("CRITICAL", f"Missing table in DB: {t}"))
        for t in extra_tables:
            events.append(("WARNING", f"Extra table in DB (missing in models): {t}"))

        # Column drift + type/nullable
        for table in sorted(model_tables & db_tables):
            model_cols = {c.name: c for c in metadata.tables[table].columns}
            db_cols = {c["name"]: c for c in inspector.get_columns(table)}

            for col in sorted(set(model_cols) - set(db_cols)):
                events.append(("CRITICAL", f"Missing column in DB: {table}.{col}"))
            for col in sorted(set(db_cols) - set(model_cols)):
                events.append(("WARNING", f"Extra column in DB: {table}.{col}"))

            for col in sorted(set(model_cols) & set(db_cols)):
                model_col = model_cols[col]
                db_col = db_cols[col]
                model_type = _normalize_type(model_col.type)
                db_type = _normalize_type(db_col.get("type"))
                if model_type and db_type and model_type != db_type:
                    events.append(
                        (
                            "CRITICAL",
                            f"Type mismatch: {table}.{col} model={model_type} db={db_type}",
                        )
                    )

                model_nullable = bool(model_col.nullable)
                db_nullable = bool(db_col.get("nullable"))
                if model_nullable != db_nullable:
                    events.append(
                        (
                            "CRITICAL",
                            f"Nullable mismatch: {table}.{col} model={model_nullable} db={db_nullable}",
                        )
                    )

        # Index drift (compare structure, not just name)
        for table in sorted(model_tables & db_tables):
            model_indexes = []
            for idx in metadata.tables[table].indexes:
                if idx.name:
                    cols = [c.name for c in idx.columns]
                    model_indexes.append((idx.name, cols, bool(idx.unique)))

            db_indexes = []
            for idx in inspector.get_indexes(table):
                name = idx.get("name")
                cols = idx.get("column_names") or []
                unique = bool(idx.get("unique"))
                if name:
                    if name.startswith("_alembic_tmp_") or name.startswith("sqlite_autoindex"):
                        continue
                    db_indexes.append((name, cols, unique))

            model_signatures = {_index_signature(cols, unique) for _, cols, unique in model_indexes}
            db_signatures = {_index_signature(cols, unique) for _, cols, unique in db_indexes}

            # name mismatch only warning if structure matches (especially for SQLite)
            if dialect == "sqlite":
                for name, cols, unique in model_indexes:
                    sig = _index_signature(cols, unique)
                    if sig in db_signatures:
                        # structure exists; name mismatch is only info
                        if name not in {n for n, _, _ in db_indexes}:
                            events.append(
                                (
                                    "WARNING",
                                    f"Index name differs but columns match: {table}.{name}",
                                )
                            )
                # only report real structural diffs
                for sig in model_signatures - db_signatures:
                    events.append(
                        (
                            "CRITICAL",
                            f"Index missing in DB (by columns): {table}.{sig[0]} unique={sig[1]}",
                        )
                    )
                for sig in db_signatures - model_signatures:
                    events.append(
                        (
                            "WARNING",
                            f"Extra index in DB (by columns): {table}.{sig[0]} unique={sig[1]}",
                        )
                    )
            else:
                # non-sqlite: compare both names and structure
                model_names = {n for n, _, _ in model_indexes}
                db_names = {n for n, _, _ in db_indexes}

                for n in sorted(model_names - db_names):
                    events.append(("CRITICAL", f"Index missing in DB: {table}.{n}"))
                for n in sorted(db_names - model_names):
                    events.append(("WARNING", f"Extra index in DB: {table}.{n}"))

                for sig in model_signatures - db_signatures:
                    events.append(
                        (
                            "CRITICAL",
                            f"Index structure mismatch (model only): {table}.{sig[0]} unique={sig[1]}",
                        )
                    )
                for sig in db_signatures - model_signatures:
                    events.append(
                        (
                            "WARNING",
                            f"Index structure mismatch (db only): {table}.{sig[0]} unique={sig[1]}",
                        )
                    )

        # UNIQUE + FK drift (skip for SQLite)
        if dialect != "sqlite":
            for table in sorted(model_tables & db_tables):
                model_uniques = {
                    c.name
                    for c in metadata.tables[table].constraints
                    if getattr(c, "unique", False) and getattr(c, "name", None)
                }
                db_uniques = {
                    u["name"] for u in inspector.get_unique_constraints(table) if u.get("name")
                }
                for uq in sorted(model_uniques - db_uniques):
                    events.append(("CRITICAL", f"Unique missing in DB: {table}.{uq}"))
                for uq in sorted(db_uniques - model_uniques):
                    events.append(("WARNING", f"Extra unique in DB: {table}.{uq}"))

            for table in sorted(model_tables & db_tables):
                model_fks = {
                    fk.constraint.name
                    for fk in metadata.tables[table].foreign_keys
                    if fk.constraint is not None and fk.constraint.name
                }
                db_fks = {
                    fk.get("name")
                    for fk in inspector.get_foreign_keys(table)
                    if fk.get("name")
                }
                for fk in sorted(model_fks - db_fks):
                    events.append(("CRITICAL", f"FK missing in DB: {table}.{fk}"))
                for fk in sorted(db_fks - model_fks):
                    events.append(("WARNING", f"Extra FK in DB: {table}.{fk}"))

    _print("SCHEMA DRIFT REPORT")
    for sev, msg in events:
        print(f"{sev}: {msg}")

    counts = _severity_counts(events)
    _print("SUMMARY")
    print("Schema drift summary:")
    print(f"Critical issues: {counts['CRITICAL']}")
    print(f"Warnings: {counts['WARNING']}")
    print(f"Informational: {counts['INFO']}")

    return 1 if counts["CRITICAL"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
