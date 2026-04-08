from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIRS = [
    ROOT / "migrations" / "versions",
    ROOT / "backend" / "migrations" / "versions",
]
STRICT_MODE = False

WARNING_RULES = [
    (r"sa\.Column\(.*nullable=False", "sa.Column(... nullable=False)"),
    (r"op\.drop_column\s*\(", "op.drop_column(...)"),
    (r"op\.drop_table\s*\(", "op.drop_table(...)"),
    (r"op\.alter_column\s*\(", "op.alter_column(...)"),
]

CRITICAL_RULES = [
    (
        r"(?is)\b(?:op|connection)\.execute\s*\(.*?\b(?:DROP\s+TABLE|DROP\s+COLUMN|DELETE\s+FROM|TRUNCATE)\b",
        "destructive SQL executed via op.execute/connection.execute",
    ),
]


def _downgrade_status(text: str) -> str:
    match = re.search(r"(?ms)^def downgrade\(\):\s*(.*)\Z", text)
    if not match:
        return "missing"

    body = match.group(1)
    normalized = re.sub(r"(?m)^\s*#.*$", "", body).strip()
    if not normalized or re.fullmatch(r"(pass\s*)+", normalized):
        return "empty"

    return "present"


def _iter_migration_files() -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for directory in MIGRATION_DIRS:
        if not directory.exists():
            continue
        for file in sorted(directory.glob("*.py")):
            resolved = file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(file)

    return files


def scan_file(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    warnings: list[str] = []
    criticals: list[str] = []

    for pattern, label in WARNING_RULES:
        if re.search(pattern, text, re.DOTALL):
            warnings.append(label)

    for pattern, label in CRITICAL_RULES:
        if re.search(pattern, text):
            criticals.append(label)

    downgrade_status = _downgrade_status(text)
    if downgrade_status == "missing":
        criticals.append("missing downgrade()")
    elif downgrade_status == "empty":
        criticals.append("empty downgrade()")

    if STRICT_MODE:
        criticals.extend(f"strict mode: {warning}" for warning in warnings)

    return warnings, criticals


def main() -> None:
    migration_files = _iter_migration_files()

    if not migration_files:
        print("Migration Guard v7")
        print("No migrations directories found")
        sys.exit(0)

    total_files = 0
    total_warnings = 0
    total_criticals = 0

    print("Migration Guard v7")
    print(f"STRICT_MODE={STRICT_MODE}")

    for file in migration_files:
        total_files += 1
        warnings, criticals = scan_file(file)

        if warnings:
            total_warnings += len(warnings)

        if criticals:
            total_criticals += len(criticals)

        if not warnings and not criticals:
            continue

        print(f"\n{file}")

        if warnings:
            print("  WARNINGS:")
            for warning in warnings:
                print(f"   - {warning}")

        if criticals:
            print("  CRITICAL:")
            for critical in criticals:
                print(f"   - {critical}")

    print("\nSummary")
    print(f" - total files scanned: {total_files}")
    print(f" - total warnings: {total_warnings}")
    print(f" - total criticals: {total_criticals}")

    if total_criticals:
        print("Result: FAIL")
        sys.exit(1)

    print("Result: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
