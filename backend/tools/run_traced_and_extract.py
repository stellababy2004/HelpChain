"""Run pytest with debug sqlite wrapper and tracemalloc, then extract application frames
for sqlite3 connection allocations printed by the debug wrapper.

This script is a helper for automated leak-fixing workflow. It will:
- set HELPCHAIN_TEST_DEBUG=1
- import debug_sqlite_connect early
- start tracemalloc
- run pytest programmatically
- scan the generated stdout log for traceback frames printed by the debug wrapper
- collect candidate file:line locations inside the repository
- write results to tools/traced_candidates.txt

Usage (from backend folder):
    python -m tools.run_traced_and_extract

Note: This script is safe to run locally and doesn't modify source.
"""

import os
import subprocess
import sys
import tracemalloc
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
LOG_DIR = HERE / "tracelogs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUT_LOG = LOG_DIR / "auto_traced_run.log"

# Ensure backend is on sys.path so debug_sqlite_connect imports
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Enable debug helper import early
os.environ.setdefault("HELPCHAIN_TEST_DEBUG", "1")
os.environ.setdefault("HELPCHAIN_TESTING", "1")

# Import the debug wrapper (best-effort)
try:
    import debug_sqlite_connect  # noqa: F401
except Exception:
    # if import fails, continue; the tests will still run
    pass

# Start tracemalloc
tracemalloc.start()

# Run pytest as a subprocess and capture output to file
with OUT_LOG.open("w", encoding="utf-8") as f:
    # Use python -c so we can import the debug wrapper inside the test process
    py_cmd = (
        "import os,sys; os.environ['HELPCHAIN_TEST_DEBUG']='1'; os.environ['HELPCHAIN_TESTING']='1';"
        "import debug_sqlite_connect; import tracemalloc; tracemalloc.start();"
        "import pytest; sys.exit(pytest.main(['-q','-W','always']))"
    )
    cmd = [sys.executable, "-c", py_cmd]
    proc = subprocess.run(
        cmd, cwd=str(HERE), stdout=f, stderr=subprocess.STDOUT, shell=False
    )
    rc = proc.returncode

# After run, parse OUT_LOG looking for debug wrapper stacks
candidates = set()
with OUT_LOG.open("r", encoding="utf-8") as f:
    lines = f.readlines()

# We look for blocks where debug_sqlite_connect printed its marker then
# traceback frames of the form: '  File "C:\...\file.py", line 123, in func'
for i, line in enumerate(lines):
    if (
        "[debug_sqlite_connect] sqlite3.dbapi2.connect called" in line
        or "[debug_sqlite_connect] sqlite3.connect called" in line
    ):
        # scan following up to 20 lines for a File frame that points into repo
        for j in range(i + 1, min(i + 20, len(lines))):
            line_str = lines[j].strip()
            if line_str.startswith('File "'):
                # Example frame format: File "C:\path\to\file.py", line 123, in func
                # We'll try to extract path and line
                import re

                m = re.search(r'File "([A-Za-z]:\\[^\"]+)", line (\d+)', line_str)
                if m:
                    p = m.group(1)
                    ln = int(m.group(2))
                    # Only keep frames inside our repo folder
                    try:
                        p_rel = Path(p).resolve()
                        if str(p_rel).startswith(str(HERE)):
                            candidates.add((str(p_rel), ln))
                            break
                    except Exception:
                        continue

# Write candidates to a file
out_path = Path(__file__).resolve().parent / "traced_candidates.txt"
with out_path.open("w", encoding="utf-8") as f:
    for p, ln in sorted(candidates):
        f.write(f"{p}:{ln}\n")

print(f"pytest exit code: {rc}")
print(f"Wrote log to: {OUT_LOG}")
print(f"Found {len(candidates)} candidate frames; wrote to {out_path}")

if len(candidates) > 0:
    for p, ln in sorted(candidates):
        print(f" - {p}:{ln}")
else:
    print("No candidate application frames were found in the trace log.")

sys.exit(0)
