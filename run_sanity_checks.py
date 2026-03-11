from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_pytest(target: str) -> int:
    cmd = [sys.executable, "-m", "pytest", target]
    print(f"\n==> Running: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=Path(__file__).resolve().parent)
    return int(completed.returncode)


def main() -> int:
    targets = [
        "tests/test_system_health_smoke.py",
        "tests/test_request_flow_smoke.py",
        "tests/visual",
    ]

    exit_codes = [run_pytest(target) for target in targets]
    has_regression = any(code != 0 for code in exit_codes)

    print("\nREGRESSION DETECTED" if has_regression else "\nSYSTEM OK")
    return 1 if has_regression else 0


if __name__ == "__main__":
    raise SystemExit(main())
