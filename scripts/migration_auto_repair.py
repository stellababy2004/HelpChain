from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import NullType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIGRATIONS_DIR = ROOT / "migrations" / "versions"


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
    if name in {"integer", "int"}:
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


def _sa_type_for(model_type: Any) -> str:
    """Best-effort SQLAlchemy type constructor string."""
    name = _type_name(model_type)
    if name.lower() in {"string", "varchar"}:
        length = getattr(model_type, "length", None)
        return f"sa.String(length={length})" if length else "sa.String()"
    if name.lower() == "text":
        return "sa.Text()"
    if name.lower() == "integer":
        return "sa.Integer()"
    if name.lower() == "biginteger":
        return "sa.BigInteger()"
    if name.lower() == "boolean":
        return "sa.Boolean()"
    if name.lower() == "float":
        return "sa.Float()"
    if name.lower() == "datetime":
        return "sa.DateTime()"
    return f"sa.{name}()"


def _latest_revision() -> str | None:
    # best effort: use alembic ScriptDirectory
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        alembic_ini = ROOT / "migrations" / "alembic.ini"
        if not alembic_ini.exists():
            return None
        config = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(config)
        return script.get_current_head()
    except Exception:
        return None


def _collect_drift() -> Dict[str, List[Tuple[str, Any]]]:
    from backend.helpchain_backend.src.app import create_app
    from backend.extensions import db

    app = create_app()
    drift: Dict[str, List[Tuple[str, Any]]] = {
        "missing_tables": [],
        "missing_columns": [],
        "nullable_mismatch": [],
        "missing_indexes": [],
        "missing_uniques": [],
        "missing_fks": [],
    }

    with app.app_context():
        metadata = db.metadata
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name
        model_tables = {t for t in metadata.tables.keys() if t != "alembic_version"}
        db_tables = {
            t
            for t in inspector.get_table_names()
            if t != "alembic_version" and not t.startswith("_alembic_tmp_")
        }

        for t in sorted(model_tables - db_tables):
            drift["missing_tables"].append((t, None))

        for table in sorted(model_tables & db_tables):
            model_cols = {c.name: c for c in metadata.tables[table].columns}
            db_cols = {c["name"]: c for c in inspector.get_columns(table)}

            for col in sorted(set(model_cols) - set(db_cols)):
                drift["missing_columns"].append((table, model_cols[col]))

            for col in sorted(set(model_cols) & set(db_cols)):
                model_col = model_cols[col]
                db_col = db_cols[col]
                if bool(model_col.nullable) != bool(db_col.get("nullable")):
                    drift["nullable_mismatch"].append((table, model_col))

            # indexes
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
                    db_indexes.append((name, cols, unique))

            model_sig = {(tuple(cols), unique) for _, cols, unique in model_indexes}
            db_sig = {(tuple(cols), unique) for _, cols, unique in db_indexes}

            for name, cols, unique in model_indexes:
                sig = (tuple(cols), unique)
                if sig not in db_sig:
                    drift["missing_indexes"].append((table, (name, cols, unique)))

            # uniques
            model_uniques = {
                c.name
                for c in metadata.tables[table].constraints
                if getattr(c, "unique", False) and getattr(c, "name", None)
            }
            db_uniques = {
                u["name"] for u in inspector.get_unique_constraints(table) if u.get("name")
            }
            for uq in sorted(model_uniques - db_uniques):
                drift["missing_uniques"].append((table, uq))

            # FKs
            model_fks = {
                fk.constraint.name
                for fk in metadata.tables[table].foreign_keys
                if fk.constraint is not None and fk.constraint.name
            }
            db_fks = {
                fk.get("name") for fk in inspector.get_foreign_keys(table) if fk.get("name")
            }
            for fk in sorted(model_fks - db_fks):
                drift["missing_fks"].append((table, fk))

        if dialect == "sqlite":
            drift["missing_uniques"] = []
            drift["missing_fks"] = []

    return drift


def _render_migration(drift: Dict[str, List[Tuple[str, Any]]]) -> str:
    revision = datetime.now().strftime("%Y%m%d%H%M%S")
    down_revision = _latest_revision() or "None"

    upgrade_lines: List[str] = []

    for table, col in drift["missing_columns"]:
        sa_type = _sa_type_for(col.type)
        upgrade_lines.append(
            f"    op.add_column('{table}', sa.Column('{col.name}', {sa_type}, nullable={bool(col.nullable)}))"
        )

    for table, (name, cols, unique) in drift["missing_indexes"]:
        cols_list = ", ".join([f"'{c}'" for c in cols])
        upgrade_lines.append(
            f"    op.create_index('{name}', '{table}', [{cols_list}], unique={bool(unique)})"
        )

    for table, uq in drift["missing_uniques"]:
        upgrade_lines.append(
            f"    # UNIQUE constraint '{uq}' missing on {table}; manual review required"
        )

    for table, fk in drift["missing_fks"]:
        upgrade_lines.append(
            f"    # NOTE: FK '{fk}' missing in DB; manual review required"
        )

    if not upgrade_lines:
        upgrade_lines.append("    pass")

    template = f"""\
\"\"\"auto drift repair\"\"

Revision ID: auto_repair_{revision}
Revises: {down_revision}
Create Date: {datetime.utcnow().isoformat()}
\"\"\"
from alembic import op
import sqlalchemy as sa


revision = 'auto_repair_{revision}'
down_revision = '{down_revision}'
branch_labels = None
depends_on = None


def upgrade():
{chr(10).join(upgrade_lines)}


def downgrade():
    # Non-destructive repair migration (no automatic downgrade)
    pass
"""
    return template


def main() -> int:
    drift = _collect_drift()
    any_drift = any(drift[k] for k in drift)

    if not any_drift:
        print("NO SCHEMA DRIFT DETECTED")
        return 0

    print("SCHEMA DRIFT FOUND")
    if drift["missing_columns"]:
        print("Missing columns:")
        for table, col in drift["missing_columns"]:
            print(f"  {table}.{col.name}")

    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"auto_repair_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.py"
    path = MIGRATIONS_DIR / filename

    path.write_text(_render_migration(drift), encoding="utf-8")

    print("Repair migration generated:")
    print(path)

    # Validate
    validate = [sys.executable, str(ROOT / "backend" / "tools" / "migration_sandbox.py"), "validate"]
    print("Running sandbox validation...")
    if subprocess.call(validate, cwd=str(ROOT)) != 0:
        print("Validation failed. Removing generated migration.")
        try:
            path.unlink()
        except Exception:
            pass
        return 1

    print("Validation passed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
