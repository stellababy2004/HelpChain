from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations" / "versions"
ALEMBIC_INI = ROOT / "migrations" / "alembic.ini"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESTRUCTIVE_SQL_PATTERNS = (
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("DROP COLUMN", re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)),
    ("DELETE FROM", re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)),
    ("TRUNCATE", re.compile(r"\bTRUNCATE(?:\s+TABLE)?\b", re.IGNORECASE)),
)


@dataclass
class GuardResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: GuardResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    current: ast.expr = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _function(module: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _is_empty_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    meaningful_nodes = [
        node
        for node in function.body
        if not (
            isinstance(node, ast.Pass)
            or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        )
    ]
    return not meaningful_nodes


def _scan_upgrade(function: ast.FunctionDef | ast.AsyncFunctionDef, path: Path) -> GuardResult:
    result = GuardResult()
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            call_name = _call_name(node)
            short_name = call_name.rsplit(".", 1)[-1]

            if call_name in {"op.drop_table", "op.drop_column"}:
                result.errors.append(f"{path}: destructive operation in upgrade(): {call_name}")
            elif call_name in {"op.alter_column", "op.batch_alter_table", "op.drop_index"}:
                result.warnings.append(f"{path}: review operation in upgrade(): {call_name}")

            if short_name == "Column" and any(
                keyword.arg == "nullable"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is False
                for keyword in node.keywords
            ):
                result.warnings.append(
                    f"{path}: adding a nullable=False column in upgrade() requires review"
                )

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for label, pattern in DESTRUCTIVE_SQL_PATTERNS:
                if pattern.search(node.value):
                    result.errors.append(f"{path}: destructive SQL in upgrade(): {label}")

    result.errors = list(dict.fromkeys(result.errors))
    result.warnings = list(dict.fromkeys(result.warnings))
    return result


def scan_migration_file(path: Path) -> GuardResult:
    result = GuardResult()
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        result.errors.append(f"{path}: unable to parse migration: {exc}")
        return result

    upgrade = _function(module, "upgrade")
    if upgrade is None:
        result.errors.append(f"{path}: missing upgrade()")
    else:
        result.extend(_scan_upgrade(upgrade, path))

    downgrade = _function(module, "downgrade")
    if downgrade is None:
        result.warnings.append(f"{path}: missing downgrade()")
    elif _is_empty_function(downgrade):
        result.warnings.append(f"{path}: empty downgrade()")

    return result


def validate_alembic_heads(alembic_ini: Path = ALEMBIC_INI) -> GuardResult:
    result = GuardResult()
    if not alembic_ini.exists():
        result.errors.append(f"Alembic config not found: {alembic_ini}")
        return result

    try:
        config = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(config)
        heads = list(script.get_heads())
    except Exception as exc:
        result.errors.append(f"Unable to inspect Alembic heads: {exc}")
        return result

    if len(heads) != 1:
        result.errors.append(f"Expected exactly one Alembic head, found {len(heads)}: {heads}")
    return result


def run_guard(changed_files: Iterable[Path], alembic_ini: Path = ALEMBIC_INI) -> GuardResult:
    result = validate_alembic_heads(alembic_ini)
    for path in changed_files:
        result.extend(scan_migration_file(path))
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Alembic graph and explicitly changed migrations."
    )
    parser.add_argument(
        "changed_migrations",
        nargs="*",
        type=Path,
        help="New or changed migration files to scan; historical files are not scanned by default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_guard(args.changed_migrations)

    if result.warnings:
        print("\nMigration Guard warnings:\n")
        for warning in result.warnings:
            print(" -", warning)

    if result.errors:
        print("\nMigration Guard FAILED:\n")
        for error in result.errors:
            print(" -", error)
        return 1

    print("Migration Guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
