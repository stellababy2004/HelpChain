"""Run the mandatory local quality gate before publication.

The gate is read-only with respect to application data and never deploys.
The visual audit requires a local server at --base-url; an unavailable browser
or server is reported as BLOCKED and returns a non-zero exit code.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(label: str, command: list[str]) -> int:
    print(f"\n== {label} ==")
    completed = subprocess.run(command, cwd=ROOT)
    print(f"{label}: {'PASS' if completed.returncode == 0 else 'FAIL'}")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    args = parser.parse_args()
    started = time.perf_counter()

    failures = []
    if run("git diff --check", ["git", "diff", "--check"]):
        failures.append("git diff --check")
    test_paths = [
        "tests/test_public_lightbox.py",
        "tests/test_navigation_layout_contract.py",
        "tests/test_public_mobile_nav_playwright.py",
    ]
    if args.mode == "full":
        test_paths = []
    pytest_root = ROOT / "tmp" / "quality-gate-pytest"
    pytest_root.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix=f"{args.mode}-", dir=pytest_root))
    pytest_command = [PYTHON, "-m", "pytest", "-q", "--basetemp", str(basetemp)] + test_paths
    if args.mode == "full":
        pytest_command = [PYTHON, "-m", "pytest", "-q", "--basetemp", str(basetemp)]
    if run(f"{args.mode} pytest", pytest_command):
        failures.append("critical pytest")
    audit = [PYTHON, str(ROOT / "scripts" / "public_visual_audit.py"), "--base-url", args.base_url, "--mode", args.mode]
    if args.mode == "fast":
        audit.append("--no-screenshots")
    if run("responsive Playwright audit", audit):
        failures.append("responsive Playwright audit")

    print("\nHELPCHAIN QUALITY GATE")
    print(f"MODE={args.mode.upper()} ELAPSED_SECONDS={time.perf_counter() - started:.2f}")
    if failures:
        print("FAIL/BLOCKED: " + ", ".join(failures))
        return 1
    print("PASS: all mandatory checks completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
