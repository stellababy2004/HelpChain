from __future__ import annotations

import re
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations" / "versions"
ALEMBIC_INI = ROOT / "migrations" / "alembic.ini"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DANGEROUS_PATTERNS = [
    ("batch_alter_table", r"\bbatch_alter_table\("),
    ("_alembic_tmp", r"_alembic_tmp"),
    ("DROP COLUMN", r"DROP COLUMN"),
    ("drop_column", r"\bdrop_column\("),
    ("ALTER COLUMN", r"ALTER COLUMN"),
    ("alter_column", r"\balter_column\("),
]

errors: list[str] = []


def _iter_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.py"))


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


def check_duplicate_indexes() -> None:
    seen: dict[str, Path] = {}
    patterns = [
        re.compile(r"""(?:op|batch_op)\.create_index\(\s*["']([^"']+)["']"""),
        re.compile(r"""CREATE\s+(?:UNIQUE\s+)?INDEX(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z0-9_]+)"""),
    ]

    for file in _iter_migration_files():
        content = file.read_text(encoding="utf-8")
        file_seen: set[str] = set()

        for pattern in patterns:
            for match in pattern.finditer(content):
                index_name = match.group(1)
                if index_name in file_seen:
                    continue
                file_seen.add(index_name)

                if index_name in seen:
                    errors.append(
                        f"Duplicate index creation: {index_name} in {file} and {seen[index_name]}"
                    )
                else:
                    seen[index_name] = file


def check_dangerous_patterns() -> None:
    for file in _iter_migration_files():
        content = file.read_text(encoding="utf-8")
        upgrade_body = _extract_upgrade_body(content)

        for label, pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, upgrade_body):
                errors.append(f"{file}: contains dangerous pattern '{label}'")


def check_multiple_heads() -> None:
    if not ALEMBIC_INI.exists():
        errors.append(f"Alembic config not found: {ALEMBIC_INI}")
        return

    try:
        config = Config(str(ALEMBIC_INI))
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
    except Exception as exc:
        errors.append(f"Unable to inspect Alembic heads: {exc}")
        return

    if len(heads) > 1:
        errors.append(f"Multiple migration heads detected: {list(heads)}")


def main() -> None:
    if not MIGRATIONS_DIR.exists():
        print("No migrations directory found.")
        sys.exit(0)

    check_dangerous_patterns()
    check_duplicate_indexes()
    check_multiple_heads()

    if errors:
        print("\nMigration Guard FAILED\n")

        for err in errors:
            print(" -", err)

        sys.exit(1)

    print("Migration Guard passed.")


if __name__ == "__main__":
    main()
