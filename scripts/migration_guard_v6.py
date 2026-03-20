from __future__ import annotations

import os
import re
import shutil
import subprocess
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
TMP_DIR = ROOT / ".tmp" / "migration_guard_v6"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

errors: list[str] = []
warnings: list[str] = []
fixes: list[str] = []


def get_database_url() -> str:
    from backend.helpchain_backend.src.config import Config

    return Config.SQLALCHEMY_DATABASE_URI


def get_models_metadata():
    import backend.models  # noqa: F401
    from backend.extensions import db

    return db.metadata


def get_db_schema(database_url: str):
    engine = create_engine(database_url)
    inspector = inspect(engine)
    schema = {}

    for table in inspector.get_table_names():
        columns = {col["name"]: col for col in inspector.get_columns(table)}
        indexes = {
            idx["name"]
            for idx in inspector.get_indexes(table)
            if idx.get("name")
            and not idx["name"].startswith("sqlite_autoindex")
            and not idx["name"].startswith("_alembic_tmp_")
        }
        schema[table] = {"columns": columns, "indexes": indexes}

    engine.dispose()
    return schema


def map_type(col) -> str:
    col_type = col.type

    if isinstance(col_type, Integer):
        return "sa.Integer()"
    if isinstance(col_type, BigInteger):
        return "sa.BigInteger()"
    if isinstance(col_type, Float):
        return "sa.Float()"
    if isinstance(col_type, Boolean):
        return "sa.Boolean()"
    if isinstance(col_type, DateTime):
        return "sa.DateTime()"
    if isinstance(col_type, Date):
        return "sa.Date()"

    type_name = col_type.__class__.__name__
    if hasattr(col_type, "length") and getattr(col_type, "length", None):
        return f"sa.{type_name}(length={col_type.length})"

    return f"sa.{type_name}()"


def detect_drift(db_schema, metadata) -> None:
    for table in metadata.tables.values():
        table_name = table.name

        if table_name == "alembic_version" or table_name.startswith("_alembic_tmp_"):
            continue

        if table_name not in db_schema:
            warnings.append(f"Table missing in migrated DB: {table_name}")
            fixes.append(f"# create table migration needed for '{table_name}'")
            continue

        db_cols = db_schema[table_name]["columns"]
        db_idx = db_schema[table_name]["indexes"]

        for col in table.columns:
            if col.primary_key or col.name in db_cols:
                continue

            fixes.append(
                f'op.add_column("{table_name}", sa.Column("{col.name}", {map_type(col)}, nullable=True))'
            )

        for idx in table.indexes:
            if not idx.name or idx.name in db_idx:
                continue

            cols = [c.name for c in idx.columns]
            fixes.append(
                f'op.create_index("{idx.name}", "{table_name}", {cols!r}, unique={bool(idx.unique)})'
            )


def check_heads() -> list[str]:
    if not ALEMBIC_INI.exists():
        errors.append(f"Alembic config missing: {ALEMBIC_INI}")
        return []

    try:
        config = AlembicConfig(str(ALEMBIC_INI))
        script = ScriptDirectory.from_config(config)
        heads = list(script.get_heads())
    except Exception as exc:
        errors.append(f"Unable to inspect migration heads: {exc}")
        return []

    if len(heads) > 1:
        errors.append(f"Multiple heads detected: {heads}")

    return heads


def _extract_upgrade_body(content: str) -> str:
    lines = content.splitlines()
    in_upgrade = False
    collected: list[str] = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("def upgrade"):
            in_upgrade = True
            continue

        if in_upgrade and stripped.startswith("def downgrade"):
            break

        if in_upgrade:
            collected.append(line)

    return "\n".join(collected)


def scan_migrations() -> None:
    dangerous_patterns = [
        ("batch_alter_table", r"\bbatch_alter_table\("),
        ("alter_column", r"\balter_column\("),
        ("_alembic_tmp", r"_alembic_tmp"),
    ]

    for file in sorted(MIGRATIONS_DIR.glob("*.py")):
        txt = file.read_text(encoding="utf-8")
        upgrade_body = _extract_upgrade_body(txt)

        for label, pattern in dangerous_patterns:
            if re.search(pattern, upgrade_body):
                errors.append(f"{file}: {label} -> rebuild risk")


def generate_fix(write_fix: bool, heads: list[str]) -> Path | None:
    if not fixes:
        return None

    if not write_fix:
        return None

    if len(heads) != 1:
        errors.append("Cannot auto-generate fix migration with multiple/no heads")
        return None

    revision = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    file = MIGRATIONS_DIR / f"{revision}_auto_fix.py"
    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    code = f'''"""
auto fix migration

Revision ID: {revision}
Revises: {heads[0]}
Create Date: {created_at}
"""

from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = "{heads[0]}"
branch_labels = None
depends_on = None


def upgrade():
'''

    for fix in fixes:
        code += f"    {fix}\n"

    code += """


def downgrade():
    pass
"""

    file.write_text(code, encoding="utf-8")
    return file


def simulate_upgrade() -> None:
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    db_path = TMP_DIR / "test.db"
    test_url = f"sqlite:///{db_path.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = test_url
    env["SQLALCHEMY_DATABASE_URI"] = test_url
    env["HC_DB_PATH"] = db_path.as_posix()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "backend.appy:app",
            "db",
            "upgrade",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        errors.append("Migration simulation failed")
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            warnings.append(f"Simulation output: {detail.splitlines()[-1]}")


def estimate() -> int:
    score = 10

    if errors:
        score -= 5

    if fixes:
        score -= 2

    if any("batch" in error for error in errors):
        score -= 3

    return max(score, 1)


def main() -> None:
    write_fix = "--write-fix" in sys.argv

    if not MIGRATIONS_DIR.exists():
        print("No migrations directory")
        sys.exit(0)

    heads = check_heads()
    scan_migrations()
    simulate_upgrade()

    metadata = get_models_metadata()
    sandbox_url = f"sqlite:///{(TMP_DIR / 'test.db').as_posix()}"
    if (TMP_DIR / "test.db").exists():
        db_schema = get_db_schema(sandbox_url)
        detect_drift(db_schema, metadata)

    fix_file = generate_fix(write_fix, heads)
    score = estimate()

    print("\n=== MIGRATION GUARD V6 ===\n")

    print("Warnings:")
    for warning in warnings:
        print(" -", warning)

    print("\nErrors:")
    for error in errors:
        print(" -", error)

    if fixes:
        print("\nSuggested fixes:")
        for fix in fixes:
            print(" -", fix)

    if fix_file:
        print(f"\nAuto-fix generated: {fix_file}")

    print("\nSafety score:", score, "/10")

    if errors:
        print("\nFAIL")
        sys.exit(1)

    print("\nPASS")


if __name__ == "__main__":
    main()
