"""Deprecate local passwords for accounts bound to Microsoft OIDC.

This script marks `password_disabled=1` for users who have a non-empty `ms_oid`.
It supports dry-run mode, exclusion lists, threshold enforcement, and CSV export
of affected accounts. Break-glass admin account(s) can be excluded explicitly.

Usage examples (PowerShell):
    # Dry run summary
    .\.venv\Scripts\python.exe .\scripts\deprecate_local_passwords.py --dry-run

    # Execute changes (after reviewing dry-run)
    .\.venv\Scripts\python.exe .\scripts\deprecate_local_passwords.py --commit

    # Export affected users to CSV during dry-run
    .\.venv\Scripts\python.exe .\scripts\deprecate_local_passwords.py --dry-run --export-csv affected.csv

    # Require at least 80% bound before proceeding
    .\.venv\Scripts\python.exe .\scripts\deprecate_local_passwords.py --commit --min-bound-percent 80

Security Notes:
- Does NOT remove or overwrite legacy password hashes yet (purge is separate phase).
- Ensures idempotency: running twice will not re-disable already disabled accounts.
- Uses direct DB access (no Flask app import) to avoid side effects.
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_FILE = INSTANCE_DIR / "volunteers.db"
DB_URI = f"sqlite:///{DB_FILE}"  # SQLAlchemy URI


def connect_engine() -> Engine:
    if not DB_FILE.exists():
        raise SystemExit(
            f"Database file not found: {DB_FILE}. Start app once to create it."
        )
    return create_engine(DB_URI, future=True)


def fetch_users(engine: Engine):
    sql = text("SELECT id, username, email, ms_oid, password_disabled FROM users")
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql).fetchall()]


def determine_targets(rows: list[dict], excludes: set[str]) -> list[dict]:
    targets: list[dict] = []
    for r in rows:
        ms_oid = (r.get("ms_oid") or "").strip()
        if not ms_oid:
            continue
        if r.get("password_disabled") in (1, True):
            continue
        username = str(r.get("username") or "")
        if username in excludes:
            continue
        targets.append(r)
    return targets


def bound_stats(rows: list[dict]):
    total = len(rows)
    bound = sum(1 for r in rows if (r.get("ms_oid") or "").strip())
    disabled = sum(1 for r in rows if r.get("password_disabled") in (1, True))
    return total, bound, disabled


def disable_targets(engine: Engine, targets: list[dict]):
    if not targets:
        return 0
    ids = [t["id"] for t in targets]
    # Chunking for very large sets (unlikely here but safer)
    updated = 0
    with engine.begin() as conn:
        for chunk_start in range(0, len(ids), 500):
            chunk = ids[chunk_start : chunk_start + 500]
            conn.execute(
                text(
                    "UPDATE users SET password_disabled=1 WHERE id IN ("
                    + ",".join(str(i) for i in chunk)
                    + ")"
                )
            )
            updated += len(chunk)
    return updated


def export_csv(path: Path, rows: Sequence[dict]):
    if not rows:
        return
    fieldnames = ["id", "username", "email", "ms_oid"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def parse_args():
    p = argparse.ArgumentParser(
        description="Deprecate local passwords for bound accounts."
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show what would change.")
    mode.add_argument("--commit", action="store_true", help="Apply changes.")
    p.add_argument(
        "--exclude",
        nargs="*",
        default=["admin"],
        help="Usernames to exclude (break-glass).",
    )
    p.add_argument(
        "--min-bound-percent",
        type=int,
        default=0,
        help="Require at least this % of accounts bound (0-100) before commit.",
    )
    p.add_argument(
        "--export-csv",
        type=Path,
        help="CSV file to write affected users (dry-run or commit).",
    )
    return p.parse_args()


def main():
    args = parse_args()
    engine = connect_engine()
    rows = fetch_users(engine)
    total, bound, disabled = bound_stats(rows)
    excludes = set(args.exclude)

    targets = determine_targets(rows, excludes)
    bound_percent = (bound / total * 100) if total else 0.0

    print("=== Password Deprecation Summary ===")
    print(f"Total users: {total}")
    print(f"Bound (ms_oid): {bound}")
    print(f"Bound percent: {bound_percent:.2f}%")
    print(f"Already password-disabled: {disabled}")
    print(f"Candidates to disable now: {len(targets)}")
    print(
        f"Excluded usernames: {', '.join(sorted(excludes)) if excludes else '(none)'}"
    )

    if args.min_bound_percent and bound_percent < args.min_bound_percent:
        print(
            f"ABORT: Bound percent {bound_percent:.2f}% < required {args.min_bound_percent}%."
        )
        return

    if args.export_csv:
        export_csv(args.export_csv, targets)
        print(f"Exported {len(targets)} target users to {args.export_csv}")

    if args.dry_run:
        print("Dry-run: no changes applied.")
        return

    updated = disable_targets(engine, targets)
    print(f"Updated (password_disabled=1): {updated}")
    print("Done.")


if __name__ == "__main__":
    main()
