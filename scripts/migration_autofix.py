from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations" / "versions"


SAFE_IMPORT = (
    "from backend.db.migration_utils import "
    "safe_create_fk, safe_create_index, safe_create_unique_constraint, "
    "safe_drop_column, safe_drop_constraint, safe_drop_index"
)


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd, cwd=str(ROOT))


def _drift_detected() -> bool:
    cmd = [sys.executable, str(ROOT / "backend" / "tools" / "migration_drift_detector.py")]
    return _run(cmd) != 0


def _latest_migration() -> Path | None:
    if not MIGRATIONS_DIR.exists():
        return None
    files = list(MIGRATIONS_DIR.glob("*.py"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _patch_migration(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    original = text

    # Inject safe helpers import
    if "backend.db.migration_utils" not in text:
        lines = text.splitlines()
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and line.startswith("import sqlalchemy"):
                new_lines.append(SAFE_IMPORT)
                inserted = True
        if not inserted:
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if not inserted and line.startswith("from alembic import op"):
                    new_lines.append(SAFE_IMPORT)
                    inserted = True
        text = "\n".join(new_lines)

    # Replace unsafe operations
    text = text.replace("op.drop_index(", "safe_drop_index(op, ")
    text = text.replace("op.drop_constraint(", "safe_drop_constraint(op, ")
    text = text.replace("op.drop_column(", "safe_drop_column(op, ")

    text = text.replace("op.create_index(", "safe_create_index(op, ")
    text = text.replace("op.create_unique_constraint(", "safe_create_unique_constraint(op, ")
    text = text.replace("op.create_foreign_key(", "safe_create_fk(op, ")

    if text != original:
        path.write_text(text, encoding="utf-8")


def main() -> int:
    if not _drift_detected():
        print("NO SCHEMA DRIFT DETECTED")
        return 0

    print("SCHEMA DRIFT FOUND")
    print("Generating migration...")

    cmd = [
        sys.executable,
        "-m",
        "flask",
        "--app",
        "backend.appy:app",
        "db",
        "revision",
        "--autogenerate",
        "-m",
        "auto drift repair",
    ]
    if _run(cmd) != 0:
        print("FAILED TO GENERATE MIGRATION")
        return 1

    latest = _latest_migration()
    if not latest:
        print("NO MIGRATION FILE FOUND")
        return 1

    _patch_migration(latest)

    print("Created migration:")
    print(str(latest))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
