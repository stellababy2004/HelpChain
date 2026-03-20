from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"


CRITICAL_PATTERNS = [
    r"drop_column",
    r"drop_table",
    r"drop_constraint",
]

HIGH_RISK_PATTERNS = [
    r"alter_column",
]

MEDIUM_PATTERNS = [
    r"create_index",
]

SAFE_PATTERNS = [
    r"add_column",
    r"create_table",
]


def classify(line: str) -> str | None:

    for p in CRITICAL_PATTERNS:
        if re.search(p, line):
            return "CRITICAL"

    for p in HIGH_RISK_PATTERNS:
        if re.search(p, line):
            return "HIGH"

    for p in MEDIUM_PATTERNS:
        if re.search(p, line):
            return "MEDIUM"

    for p in SAFE_PATTERNS:
        if re.search(p, line):
            return "SAFE"

    return None


def analyze_file(path: Path) -> List[Dict]:

    findings = []

    text = path.read_text(encoding="utf-8")

    for i, line in enumerate(text.splitlines(), start=1):

        level = classify(line)

        if level:
            findings.append(
                {
                    "level": level,
                    "line": i,
                    "code": line.strip(),
                }
            )

    return findings


def main() -> int:

    print("\nMigration Risk Analyzer\n")

    files = sorted(MIGRATIONS.glob("*.py"))

    critical = 0
    high = 0
    medium = 0

    for f in files:

        findings = analyze_file(f)

        if not findings:
            continue

        print(f"\n{f.name}")

        for item in findings:

            lvl = item["level"]

            if lvl == "CRITICAL":
                critical += 1

            elif lvl == "HIGH":
                high += 1

            elif lvl == "MEDIUM":
                medium += 1

            print(
                f"{lvl:8} line {item['line']:4} | {item['code']}"
            )

    print("\nSummary")

    print("Critical:", critical)
    print("High:", high)
    print("Medium:", medium)

    if critical > 0:
        print("\nCRITICAL migration risk detected")
        return 1

    print("\nMigration risk acceptable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
