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

import os
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

    # If the sanity check passed, prefer running Alembic programmatically
    # inside this process. That allows us to push a Flask application
    # context (if available) so env.py can access current_app.extensions.
    try:
        import alembic

        alembic_command = alembic.command
        AlembicConfig = alembic.config.Config
    except Exception:
        AlembicConfig = None  # type: ignore

    # Helper to attempt to create and push a Flask app context. Returns
    # the context object if pushed (so we can pop it later), otherwise None.
    app_ctx = None
    try:
        # Try common application factory location in this repository.
        # This import is best-effort; if it fails we fall back to running
        # alembic as a subprocess which will surface the same error.
        try:
            # Ensure repo root (parent of this backend/ dir) is on sys.path so
            # imports like 'backend.models' resolve correctly when this script
            # is executed from inside backend/ (as CI does).
            repo_root = Path(__file__).resolve().parent.parent
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            from helpchain_backend.src.app import Config as AppConfig
            from helpchain_backend.src.app import create_app  # type: ignore

            # Use a lightweight config for migrations to avoid connecting to
            # external DBs during app creation (create_app calls db.create_all()).
            class _MigrateConfig(AppConfig):
                SQLALCHEMY_DATABASE_URI = os.environ.get(
                    "SQLALCHEMY_DATABASE_URI",
                    os.environ.get("DATABASE_URL", "sqlite:///:memory:"),
                )

            app = create_app(_MigrateConfig)
            app_ctx = app.app_context()
            app_ctx.push()
            print("Pushed Flask application context for migrations.")
        except Exception as e:
            # If creating the app fails, print the exception so diagnostics
            # are visible in CI/local runs, then continue to fallback paths.
            print(
                f"Could not create Flask app (will try fallback): {e}", file=sys.stderr
            )
            app_ctx = None

        if AlembicConfig is not None:
            print(f"Running alembic programmatically with: {ini}")
            alembic_cfg = AlembicConfig(str(ini))
            alembic_command.upgrade(alembic_cfg, "head")
            return 0
        # Fall back to subprocess if alembic package isn't importable.
        cmd = ["alembic", "-c", str(ini), "upgrade", "head"]
        print(f"Running subprocess: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return 0
    except FileNotFoundError:
        print(
            "ERROR: 'alembic' command not found. Is Alembic installed in this environment?",
            file=sys.stderr,
        )
        return 3
    except Exception as exc:
        print(f"ERROR: alembic failed: {exc}", file=sys.stderr)
        return getattr(exc, "code", 3) or 3
    finally:
        if app_ctx is not None:
            try:
                app_ctx.pop()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
