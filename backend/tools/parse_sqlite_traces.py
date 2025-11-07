import re
from datetime import datetime
from pathlib import Path

TRACE_FILE = Path(__file__).resolve().parent / "sqlite_connect_traces.txt"

sep_re = re.compile(r"^--- sqlite3.connect called: (?P<ts>[^ ]+) .+ ---$")
file_re = re.compile(r"^\s*File \"(?P<file>.+?)\", line (?P<line>\d+),")


def is_in_repo(path: str) -> bool:
    p = path.replace("/", "\\")
    return ("\\helpchain_backend\\src\\" in p) or ("\\backend\\" in p)


blocks = []
if not TRACE_FILE.exists():
    print("no traces file at", TRACE_FILE)
    raise SystemExit(1)

with TRACE_FILE.open("r", encoding="utf-8", errors="replace") as fh:
    current = None
    for ln in fh:
        m = sep_re.match(ln)
        if m:
            if current:
                blocks.append(current)
            ts = m.group("ts")
            try:
                ts_dt = datetime.fromisoformat(ts)
            except Exception:
                ts_dt = None
            current = {"ts": ts_dt, "raw": [], "frames": []}
            continue
        if current is None:
            continue
        current["raw"].append(ln.rstrip("\n"))
        fm = file_re.match(ln)
        if fm:
            current["frames"].append((fm.group("file"), int(fm.group("line"))))
    if current:
        blocks.append(current)

# For each block, find the first in-repo frame (if any)
first_counts = {}
examples = {}
for b in blocks:
    first = None
    for p, ln in b["frames"]:
        if is_in_repo(p):
            # normalize to repo-relative path
            norm = p.replace("\\", "/").split("/helpchain_backend/src/")
            if len(norm) == 2:
                rel = "helpchain_backend/src/" + norm[1]
            else:
                rel = p.split("\\backend\\")[-1]
            first = f"{rel}:{ln}"
            break
    if first is None:
        # fallback: first frame outside site-packages
        for p, ln in b["frames"]:
            if "site-packages" not in p:
                first = f"{Path(p).name}:{ln}"
                break
    if first is None:
        first = "unknown"
    first_counts[first] = first_counts.get(first, 0) + 1
    if first not in examples:
        examples[first] = "\n".join(b["raw"][:20])

items = sorted(first_counts.items(), key=lambda x: x[1], reverse=True)

print("Top first-in-repo hotspots (file:line)")
for name, cnt in items[:20]:
    print(f"{cnt:6d}  {name}")

print("\nRepresentative stacks for top offenders:")
for name, cnt in items[:6]:
    print("\n---", name, f"({cnt})", "---")
    print(examples.get(name, "(no example)"))
