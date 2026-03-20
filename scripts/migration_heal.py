from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("\n>>>", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def step(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> int:

    # 1 Drift detection
    step("STEP 1: Drift Detection")

    r = run([sys.executable, "scripts/migration_drift_detector.py"])

    if r == 0:
        print("\nNo schema drift detected.")
    else:
        print("\nDrift detected. Generating repair migration.")

        # 2 Auto repair
        step("STEP 2: Generate Repair Migration")

        r = run([sys.executable, "scripts/migration_auto_repair.py"])

        if r != 0:
            print("Repair migration generation failed.")
            return 1

    # 3 Sandbox validation
    step("STEP 3: Sandbox Validation")

    r = run([sys.executable, "scripts/migration_sandbox.py", "validate"])

    if r != 0:
        print("Sandbox validation failed.")
        return 1

    # 4 Migration upgrade
    step("STEP 4: Apply Migrations")

    r = run(["flask", "db", "upgrade"])

    if r != 0:
        print("Migration upgrade failed.")
        return 1

    # 5 Final drift check
    step("STEP 5: Final Drift Check")

    r = run([sys.executable, "scripts/migration_drift_detector.py"])

    if r == 0:
        print("\nSchema successfully healed.")
        return 0

    print("\nMigration completed but drift remains.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
