"""Summarize tracemalloc sqlite connection allocation traces.

Reads backend/tools/tracemalloc_sqlite_connections.txt and groups the first
in-repo frame found in each allocation block. Prints counts and sample traces.
"""

import re
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
TRACES = ROOT / "tools" / "tracemalloc_sqlite_connections.txt"

if not TRACES.exists():
    print(f"No trace file found at {TRACES}")
    sys.exit(1)

raw = TRACES.read_text(encoding="utf-8", errors="replace")
blocks = [
    b.strip() for b in raw.split("--- sqlite3.Connection allocation ---") if b.strip()
]

frame_re = re.compile(r'File "([^"]+)", line (\d+)')

from collections import Counter, defaultdict

counts = Counter()
examples = defaultdict(list)

for blk in blocks:
    frames = frame_re.findall(blk)
    # frames is list of (path, lineno) in the order they appear in the file
    first_inrepo = None
    for path, lineno in frames:
        try:
            p = Path(path).resolve()
            # consider in-repo if path is inside the backend repo root
            if str(p).startswith(str(ROOT)):
                first_inrepo = (str(p), int(lineno))
                break
        except Exception:
            # fallback: simple substring match for 'backend' folder
            if "backend" in path and "site-packages" not in path:
                try:
                    first_inrepo = (path, int(lineno))
                    break
                except Exception:
                    continue
    if first_inrepo is None and frames:
        # fallback: take the first frame that looks like it's from project (not venv/site-packages)
        for path, lineno in frames:
            if "site-packages" in path or ".venv" in path or "dist-packages" in path:
                continue
            first_inrepo = (path, int(lineno))
            break
    key = first_inrepo or ("<no-inrepo-frame>", 0)
    counts[key] += 1
    if len(examples[key]) < 3:
        # store a small excerpt of the block as example
        excerpt = "\n".join(blk.splitlines()[:12])
        examples[key].append(excerpt)

# Print summary sorted
print(f"Parsed {len(blocks)} sqlite3.Connection allocation blocks from {TRACES}\n")

most = counts.most_common()
if not most:
    print("No frames detected")
    sys.exit(0)

print("Top in-repo allocation roots (file:line) and counts:\n")
for (path, lineno), cnt in most[:25]:
    print(f"{cnt:4d}  {path}:{lineno}")

print("\nDetailed examples for top frames:\n")
for (path, lineno), cnt in most[:6]:
    print(f"=== {cnt} occurrences — {path}:{lineno} ===")
    exs = examples[(path, lineno)]
    for i, e in enumerate(exs, 1):
        print(f"--- example {i} ---")
        print(e)
        print()

# Also report whether appy.py appears among top frames
appy_hits = [
    (k, v)
    for k, v in counts.items()
    if isinstance(k[0], str) and k[0].endswith("appy.py")
]
if appy_hits:
    print("\nappy.py frames detected:")
    for (p, lineno), v in appy_hits:
        print(f"{v}x  {p}:{lineno}")
else:
    print("\nNo direct appy.py top frames detected.")

# Exit
sys.exit(0)
