from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"
ALEMBIC_INI = ROOT / "migrations" / "alembic.ini"
TMP_DIR = ROOT / ".tmp"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

errors: list[str] = []
warnings: list[str] = []
fixes: list[str] = []


def get_models_metadata():
    import backend.models  # noqa: F401
    from backend.extensions import db

    schema: dict[str, dict[str, set[str]]] = {}

    for table in db.metadata.tables.values():
        schema[table.name] = {
            "columns": {col.name for col in table.columns},
            "indexes": {idx.name for idx in table.indexes if idx.name},
        }

    return schema


def get_db_schema(database_url: str):
    engine = create_engine(database_url)
    inspector = inspect(engine)

    schema: dict[str, dict[str, set[str]]] = {}

    for table in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns(table)]
        indexes = [
            idx["name"]
            for idx in inspector.get_indexes(table)
            if idx.get("name")
            and not idx["name"].startswith("sqlite_autoindex")
            and not idx["name"].startswith("_alembic_tmp_")
        ]

        schema[table] = {
            "columns": set(columns),
            "indexes": set(indexes),
        }

    engine.dispose()
    return schema


def detect_schema_drift(db_schema, model_schema):
    for table, model_info in model_schema.items():
        if table == "alembic_version" or table.startswith("_alembic_tmp_"):
            continue

        if table not in db_schema:
            errors.append(f"Table '{table}' missing in migrated DB")
            fixes.append(f"Create or repair migration for missing table '{table}'")
            continue

        model_cols = model_info["columns"]
        db_cols = db_schema[table]["columns"]

        missing_cols = sorted(model_cols - db_cols)
        extra_cols = sorted(db_cols - model_cols)

        for col in missing_cols:
            errors.append(f"{table}: missing column in DB -> {col}")
            fixes.append(f"Generate migration to add '{table}.{col}'")

        for col in extra_cols:
            warnings.append(f"{table}: extra column in DB -> {col}")

        model_idx = {idx for idx in model_info["indexes"] if idx}
        db_idx = db_schema[table]["indexes"]
        missing_idx = sorted(model_idx - db_idx)

        for idx in missing_idx:
            warnings.append(f"{table}: missing index -> {idx}")
            fixes.append(f"Add index migration for '{idx}' on '{table}'")


def scan_migrations():
    dangerous_patterns = [
        ("batch_alter_table", r"\bbatch_alter_table\("),
        ("alter_column", r"\balter_column\("),
        ("drop_column", r"\bdrop_column\("),
        ("server_default", r"server_default\s*="),
        ("_alembic_tmp", r"_alembic_tmp"),
    ]

    for file in sorted(MIGRATIONS.glob("*.py")):
        content = file.read_text(encoding="utf-8")

        for label, pattern in dangerous_patterns:
            if re.search(pattern, content):
                if label in {"batch_alter_table", "alter_column"}:
                    warnings.append(f"{file}: SQLite rebuild risk -> {label}")
                else:
                    errors.append(f"{file}: dangerous pattern -> {label}")


def check_heads():
    if not ALEMBIC_INI.exists():
        errors.append(f"Alembic config missing: {ALEMBIC_INI}")
        return []

    try:
        config = Config(str(ALEMBIC_INI))
        script = ScriptDirectory.from_config(config)
        heads = list(script.get_heads())
    except Exception as exc:
        errors.append(f"Unable to inspect migration heads: {exc}")
        return []

    if len(heads) > 1:
        errors.append(f"Multiple heads: {heads}")
        fixes.append("Create an Alembic merge revision to unify heads")

    return heads


def run_sandbox_migrations():
    TMP_DIR.mkdir(exist_ok=True)
    sandbox_dir = TMP_DIR / "migration_guard_v4"

    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir, ignore_errors=True)
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    db_path = sandbox_dir / "guard_v4.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    env = os.environ.copy()
    env["HC_DB_PATH"] = db_path.as_posix()
    env["DATABASE_URL"] = db_url
    env["SQLALCHEMY_DATABASE_URI"] = db_url

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
        errors.append("Sandbox migration failed")
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = stderr or stdout
        if details:
            warnings.append(f"Sandbox migration output: {details.splitlines()[-1]}")
        fixes.append("Repair broken migrations until `flask db upgrade` succeeds on an empty SQLite sandbox")
        return None

    return get_db_schema(db_url)


def estimate_risk():
    score = 10

    if any("SQLite rebuild risk" in w for w in warnings):
        score -= 3
    if any("Multiple heads" in e for e in errors):
        score -= 3
    if any("Sandbox migration failed" in e for e in errors):
        score -= 3
    if len(errors) > 5:
        score -= 1

    return max(score, 1)


def main():
    if not MIGRATIONS.exists():
        print("No migrations dir")
        sys.exit(0)

    try:
        model_schema = get_models_metadata()
    except Exception as exc:
        print(f"FAILED TO LOAD MODELS: {exc}")
        sys.exit(1)

    heads = check_heads()
    scan_migrations()
    db_schema = run_sandbox_migrations()

    if db_schema is not None:
        detect_schema_drift(db_schema, model_schema)

    score = estimate_risk()

    print("\n=== MIGRATION GUARD V4 REPORT ===\n")
    print("Heads:", heads)

    print("\nWarnings:")
    for warning in warnings:
        print(" -", warning)

    print("\nErrors:")
    for error in errors:
        print(" -", error)

    print("\nFix recommendations:")
    for fix in sorted(set(fixes)):
        print(" -", fix)

    print("\nProduction safety score:", score, "/10")

    if errors:
        print("\nMigration Guard v4 FAILED")
        sys.exit(1)

    print("\nMigration Guard v4 PASSED")


if __name__ == "__main__":
    main()
