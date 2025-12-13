#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("artifacts/file_scan_analysis.json")
if not p.exists():
    print("file not found:", p)
    raise SystemExit(1)
obj = json.load(p.open())
for i, f in enumerate(obj.get("findings", [])[:50]):
    print(
        f"{i+1}. count={f['count']:>5} files={len(f['files']):>4} value={f['value'][:120]!r}"
    )
