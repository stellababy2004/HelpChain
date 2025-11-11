#!/usr/bin/env python3
"""Run alembic migrations with a small sanity check for the INI file.

This script ensures the first meaningful line of migrations/alembic.ini
starts with '[' so that accidental overwrites (for example storing a
Python file in place of the INI) fail fast with a clear message in CI.

Exit codes:
  0 - success (alembic completed or nothing to do)
  2 - alembic.ini missing or malformed (fast-fail to make CI errors obvious)
  3 - alembic command missing / invocation failed
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_alembic_ini() -> Path | None:
    # Prefer local migrations/alembic.ini when this script is run from the
    # repository's backend directory (how CI runs it). Provide a couple of
    # reasonable fallbacks so the script is forgiving in various dev setups.
    candidates = [
        Path("migrations/alembic.ini"),
        Path("backend/migrations/alembic.ini"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def first_meaningful_line(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n\r")
                if not line.strip():
                    continue
                # INI comment chars: '#' and ';'
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith(";"):
                    continue
                return line
    except OSError:
        return None
    return None


def main() -> int:
    ini = find_alembic_ini()
    if ini is None:
        print(
            "ERROR: migrations/alembic.ini not found. Expected at 'migrations/alembic.ini'.",
            file=sys.stderr,
        )
        return 2

    first = first_meaningful_line(ini)
    if not first or not first.lstrip().startswith("["):
        print(f"ERROR: {ini} does not look like a valid INI file.", file=sys.stderr)
        print(
            "Expected the first meaningful line to start with '[' (an INI section),",
            file=sys.stderr,
        )
        print("but got:\n\n", file=sys.stderr)
        if first is None:
            print("(could not read file)\n", file=sys.stderr)
        else:
            print(f"    {first!r}\n", file=sys.stderr)
        print(
            "Failing early to avoid confusing Alembic errors; please ensure the file is not overwritten.",
            file=sys.stderr,
        )
        return 2

    # If the sanity check passed, run alembic using the found INI file.
    cmd = ["alembic", "-c", str(ini), "upgrade", "head"]
    try:
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return 0
    except FileNotFoundError:
        print(
            "ERROR: 'alembic' command not found. Is Alembic installed in this environment?",
            file=sys.stderr,
        )
        return 3
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: alembic failed with return code {exc.returncode}", file=sys.stderr
        )
        return exc.returncode or 3


if __name__ == "__main__":
    raise SystemExit(main())
