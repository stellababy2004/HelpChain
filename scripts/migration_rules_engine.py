import sys
from pathlib import Path

MIGRATIONS_DIR = Path("migrations/versions")

BLOCKED_PATTERNS = [
    "batch_alter_table",
    "alter_column",
    "_alembic_tmp",
]

WARN_PATTERNS = [
    "drop_column",
    "drop_table",
    "drop_index",
]


def scan_file(file_path):
    content = file_path.read_text(encoding="utf-8")

    errors = []
    warnings = []

    for pattern in BLOCKED_PATTERNS:
        if pattern in content:
            errors.append(f"{file_path.name}: uses {pattern}")

    for pattern in WARN_PATTERNS:
        if pattern in content:
            warnings.append(f"{file_path.name}: uses {pattern}")

    return errors, warnings


def main():
    all_errors = []
    all_warnings = []

    if not MIGRATIONS_DIR.exists():
        print("No migrations directory")
        sys.exit(0)

    for file in MIGRATIONS_DIR.glob("*.py"):
        errors, warnings = scan_file(file)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    print("\n=== MIGRATION RULES ENGINE ===\n")

    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(" -", warning)

    if all_errors:
        print("\nBLOCKED MIGRATIONS:")
        for error in all_errors:
            print(" -", error)

        sys.exit(1)

    print("\nALL MIGRATIONS SAFE")


if __name__ == "__main__":
    main()
