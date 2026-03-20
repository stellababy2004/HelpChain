"""SQLite-safe Alembic helpers to reduce migration drift failures."""
from __future__ import annotations

from sqlalchemy import inspect


def _dialect_name(op) -> str:
    try:
        return op.get_bind().dialect.name
    except Exception:
        return ""


def safe_drop_index(op, index_name: str, **kwargs) -> None:
    """Drop index if it exists. SQLite often rewrites unique indexes as autoindexes."""
    if not index_name:
        return
    if _dialect_name(op) == "sqlite":
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        return
    op.drop_index(index_name, **kwargs)


def safe_drop_constraint(
    op,
    constraint_name: str | None,
    table_name: str | None = None,
    type_: str | None = None,
    **kwargs,
) -> None:
    """Drop constraint if it exists; SQLite requires named constraints and may omit names."""
    if not constraint_name:
        return
    try:
        if _dialect_name(op) == "sqlite":
            # Batch mode will rebuild tables; avoid hard failure on missing names.
            try:
                op.drop_constraint(
                    constraint_name, table_name=table_name, type_=type_, **kwargs
                )
            except Exception:
                return
        else:
            op.drop_constraint(
                constraint_name, table_name=table_name, type_=type_, **kwargs
            )
    except Exception:
        return


def safe_drop_column(op, table_name: str, column_name: str, **kwargs) -> None:
    """Drop column if it exists (SQLite requires table rebuild)."""
    if not table_name or not column_name:
        return
    try:
        inspector = inspect(op.get_bind())
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if column_name not in cols:
            return
    except Exception:
        pass
    op.drop_column(table_name, column_name, **kwargs)


def safe_create_index(
    op, table_name: str, index_name: str, columns: list[str], unique: bool = False, **kwargs
) -> None:
    """Create index only if it does not already exist."""
    if not table_name or not index_name:
        return
    try:
        inspector = inspect(op.get_bind())
        existing = {i["name"] for i in inspector.get_indexes(table_name)}
        if index_name in existing:
            return
    except Exception:
        pass
    op.create_index(index_name, table_name, columns, unique=unique, **kwargs)


def safe_create_unique_constraint(op, table_name: str, name: str, columns: list[str], **kwargs) -> None:
    """Create unique constraint only if it does not already exist (SQLite autoindexes)."""
    if not table_name or not name:
        return
    try:
        inspector = inspect(op.get_bind())
        uniques = {u["name"] for u in inspector.get_unique_constraints(table_name)}
        if name in uniques:
            return
    except Exception:
        pass
    op.create_unique_constraint(name, table_name, columns, **kwargs)


def safe_create_fk(
    op,
    name: str,
    source: str,
    referent: str,
    local_cols: list[str],
    remote_cols: list[str],
    **kwargs,
) -> None:
    """Create foreign key; SQLite can lose constraint names during rebuilds."""
    if not name or not source or not referent:
        return
    try:
        op.create_foreign_key(name, source, referent, local_cols, remote_cols, **kwargs)
    except Exception:
        return
