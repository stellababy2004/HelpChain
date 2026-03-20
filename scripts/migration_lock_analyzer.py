from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"


LOCK_PATTERNS = {
    "EXCLUSIVE_LOCK": [
        r"drop_table",
        r"drop_column",
        r"drop_constraint",
    ],
    "TABLE_REWRITE": [
        r"alter_column",
    ],
    "INDEX_BUILD": [
        r"create_index",
    ],
}


def classify_lock(line: str) -> str | None:
    for level, patterns in LOCK_PATTERNS.items():
        for p in patterns:
            if re.search(p, line):
                return level
    return None


def analyze_file(path: Path) -> List[Dict]:
    findings = []

    text = path.read_text(encoding="utf-8")

    for i, line in enumerate(text.splitlines(), start=1):
        level = classify_lock(line)

        if level:
            findings.append(
                {
                    "level": level,
                    "line": i,
                    "code": line.strip(),
                }
            )

    return findings


def severity_score(level: str) -> int:
    if level == "EXCLUSIVE_LOCK":
        return 3
    if level == "TABLE_REWRITE":
        return 2
    if level == "INDEX_BUILD":
        return 1
    return 0


def main() -> int:

    print("\nMigration Lock Analyzer\n")

    files = sorted(MIGRATIONS.glob("*.py"))

    total_score = 0

    for f in files:

        findings = analyze_file(f)

        if not findings:
            continue

        print(f"\n{f.name}")

        for item in findings:

            level = item["level"]
            score = severity_score(level)
            total_score += score

            print(
                f"{level:15} line {item['line']:4} | {item['code']}"
            )

    print("\nLock Risk Score:", total_score)

    if total_score > 100:
        print("\nHIGH RISK: migrations may cause heavy database locks")
        return 1

    if total_score > 40:
        print("\nMEDIUM RISK: migrations should be scheduled during low traffic")
        return 0

    print("\nLOW RISK: migrations unlikely to cause blocking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
