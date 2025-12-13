#!/usr/bin/env python3
import json
import re
from pathlib import Path

IN_PATH = Path("artifacts/file_scan_analysis.json")
OUT_PATH = Path("artifacts/high_confidence.json")

JWT_RE = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
KEY_PREFIX_RE = re.compile(r"^(sk-|pk-|ghp-|GITHUB_TOKEN|VERCEL|AKIA|AIza)")

data = json.load(IN_PATH.open())
findings = data.get("findings", [])

high = []
for f in findings:
    v = f.get("value", "")
    if JWT_RE.search(v) or KEY_PREFIX_RE.search(v):
        high.append(f)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(
    json.dumps({"count": len(high), "findings": high[:500]}, indent=2), encoding="utf-8"
)
print(f"Wrote {OUT_PATH} with {len(high)} high-confidence candidates")
