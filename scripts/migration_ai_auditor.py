from __future__ import annotations

import re
import sys
from pathlib import Path

MIGRATIONS_DIR = Path("migrations/versions")

DANGEROUS_PATTERNS = {
    "drop_table": re.compile(r"\bop\.drop_table\(") ,
    "drop_column": re.compile(r"\bop\.drop_column\("),
    "drop_constraint": re.compile(r"\bop\.drop_constraint\("),
    "drop_index": re.compile(r"\bop\.drop_index\("),
    "raw_sql": re.compile(r"\bop\.execute\("),
    "alter_nullable_false": re.compile(r"\balter_column\([^\)]*nullable\s*=\s*False"),
}

DOWNGRADE_EMPTY = re.compile(r"def downgrade\(\):\s*(?:#.*\s*)*(?:pass|return|\s*)", re.MULTILINE)


LARGE_TABLE_HINTS = {
    "users",
    "cases",
    "requests",
    "assignments",
    "admin_users",
    "professional_leads",
    "volunteers",
}


def _risk_level(issues: list[str]) -> str:
    if any("drop_table" in i for i in issues):
        return "HIGH"
    if any("drop_column" in i or "drop_constraint" in i or "raw_sql" in i for i in issues):
        return "MEDIUM"
    return "LOW"


def _missing_indexes(text: str) -> list[str]:
    missing = []
    for table in LARGE_TABLE_HINTS:
        if re.search(rf"create_table\(\s*['\"]{table}['\"]", text):
            if not re.search(r"create_index\(", text):
                missing.append(table)
    return missing


def audit_file(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []

    for name, pat in DANGEROUS_PATTERNS.items():
        if pat.search(text):
            issues.append(name)

    if DOWNGRADE_EMPTY.search(text):
        issues.append("downgrade_empty")

    missing_idx = _missing_indexes(text)
    for t in missing_idx:
        issues.append(f"missing_indexes_{t}")

    return issues, missing_idx


def main() -> int:
    if not MIGRATIONS_DIR.exists():
        print("migrations/versions not found")
        return 1

    risk_found = False
    print("MIGRATION AUDIT REPORT")

    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        issues, missing_idx = audit_file(path)
        if not issues:
            continue
        risk_found = True
        print("\nFile:")
        print(path)
        print("\nRisk Level:")
        print(_risk_level(issues))
        print("\nIssues:")
        for issue in issues:
            print(issue)

    return 1 if risk_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
