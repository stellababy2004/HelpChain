#!/usr/bin/env python3
"""Scan extracted artifact files for secret-like patterns and group findings."""
import json
import re
from pathlib import Path

ROOTS = [Path("artifacts/unzipped"), Path("artifacts")]
OUT = Path("artifacts/file_scan_analysis.json")

JWT_RE = re.compile(rb"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
KEY_RE = re.compile(
    rb"\b(?:sk_|pk_|ghp_|GITHUB_TOKEN|VERCEL|AIza[0-9A-Za-z-_]{20,}|AKIA[0-9A-Z]{8,})[A-Za-z0-9_\-\.]{8,}\b"
)
LONG_B64 = re.compile(rb"[A-Za-z0-9_\-]{40,}")


def find_in_bytes(b):
    s = set()
    for r in (JWT_RE, KEY_RE, LONG_B64):
        for m in r.findall(b):
            try:
                s.add(m.decode("utf-8", errors="ignore"))
            except Exception:
                s.add(str(m))
    return s


results = {}
for root in ROOTS:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if p.is_file():
            try:
                b = p.read_bytes()
            except Exception as e:
                continue
            cands = find_in_bytes(b)
            for c in cands:
                entry = results.setdefault(c, {"value": c, "count": 0, "files": set()})
                entry["count"] += 1
                entry["files"].add(str(p))

out = []
for v, e in results.items():
    out.append(
        {
            "value": v,
            "count": e["count"],
            "files": sorted(list(e["files"])),
            "suggested_action": "review-and-revoke",
        }
    )

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    json.dumps(
        {"summary_count": len(out), "findings": sorted(out, key=lambda x: -x["count"])},
        indent=2,
    ),
    encoding="utf-8",
)
print(
    f"Scanned files under {ROOTS}; found {len(out)} unique candidate values; written to {OUT}"
)
