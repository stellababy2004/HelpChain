#!/usr/bin/env python3
"""Parse a gitleaks SARIF (or a zip containing it) and print a short summary.

Usage:
  python scripts/parse_gitleaks_sarif.py path/to/results.sarif
  python scripts/parse_gitleaks_sarif.py path/to/gitleaks-results.sarif.zip

The script prints total findings, counts by level/rule, and the top findings.
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


def load_sarif(path: Path) -> dict[str, Any]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path, "r") as z:
            # find first .sarif file
            for name in z.namelist():
                if name.lower().endswith(".sarif"):
                    with z.open(name) as fh:
                        return json.load(fh)
        raise SystemExit(f"No .sarif file found inside {path}")

    with path.open("rb") as fh:
        return json.load(fh)


def summarize_sarif(sarif: dict[str, Any]) -> None:
    runs = sarif.get("runs", [])
    total = 0
    level_counts = Counter()
    rule_counts = Counter()
    examples: list[tuple[str, str, str]] = []  # (level, file:line, message)

    for run in runs:
        results = run.get("results", [])
        for r in results:
            total += 1
            level = r.get("level") or r.get("severity") or "warning"
            level_counts[level] += 1
            rule = r.get("ruleId") or r.get("rule", {}).get("id") or "<unknown>"
            rule_counts[rule] += 1

            message = ""
            msg = r.get("message") or {}
            if isinstance(msg, dict):
                message = msg.get("text") or msg.get("markdown") or ""
            else:
                message = str(msg)

            locations = r.get("locations") or []
            loc_text = "<no-location>"
            if locations:
                try:
                    loc = locations[0]
                    phys = loc.get("physicalLocation") or {}
                    artifact = phys.get("artifactLocation", {})
                    fname = artifact.get("uri") or artifact.get("index") or "<file>"
                    region = phys.get("region") or {}
                    line = region.get("startLine") or region.get("endLine") or "?"
                    loc_text = f"{fname}:{line}"
                except Exception:
                    loc_text = "<bad-location>"

            examples.append((level, loc_text, message.strip()))

    print(f"Total findings: {total}")
    if total == 0:
        return

    print("\nBy level:")
    for lvl, cnt in level_counts.most_common():
        print(f"  {lvl}: {cnt}")

    print("\nTop rules:")
    for rule, cnt in rule_counts.most_common(20):
        print(f"  {rule}: {cnt}")

    print("\nExamples (top 20):")
    for i, (lvl, loc, msg) in enumerate(examples[:20], start=1):
        short_msg = msg.splitlines()[0][:200]
        print(f"{i:2d}. [{lvl}] {loc} — {short_msg}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    p = Path(argv[1])
    if not p.exists():
        print(f"File not found: {p}")
        return 2

    try:
        sarif = load_sarif(p)
    except Exception as e:
        print(f"Failed to load SARIF: {e}")
        return 1

    summarize_sarif(sarif)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
