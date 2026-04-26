from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.appy import app
from backend.extensions import db
from backend.models import AdminUser, Structure


STRUCTURES = [
    {"name": "Paris", "slug": "paris"},
    {"name": "Boulogne-Billancourt", "slug": "boulogne-billancourt"},
    {"name": "Neuilly-sur-Seine", "slug": "neuilly-sur-seine"},
]


def upsert_structure(name: str, slug: str, dry_run: bool) -> str:
    existing = Structure.query.filter_by(slug=slug).first()

    if existing:
        return f"SKIP structure exists: {name} ({slug})"

    if dry_run:
        return f"DRY-RUN create structure: {name} ({slug})"

    structure = Structure(
        name=name,
        slug=slug,
        status="active",
        created_at=datetime.now(UTC),
    )
    db.session.add(structure)
    return f"CREATE structure: {name} ({slug})"


def ensure_superadmin(dry_run: bool) -> str:
    username = os.getenv("HC_BOOTSTRAP_ADMIN_USERNAME", "admin")
    email = os.getenv("HC_BOOTSTRAP_ADMIN_EMAIL", "contact@helpchain.live")
    password = os.getenv("HC_BOOTSTRAP_ADMIN_PASSWORD")

    existing = AdminUser.query.filter_by(username=username).first()

    if existing:
        return f"SKIP admin exists: {username} ({existing.role})"

    if not password:
        return (
            "SKIP admin creation: HC_BOOTSTRAP_ADMIN_PASSWORD is not set. "
            "Structures can still be bootstrapped."
        )

    default_structure = Structure.query.filter_by(slug="paris").first()

    if dry_run:
        return f"DRY-RUN create superadmin: {username} / {email}"

    admin = AdminUser(
        username=username,
        email=email,
        role="superadmin",
        is_active=True,
        structure_id=default_structure.id if default_structure else None,
    )
    admin.set_password(password)
    db.session.add(admin)

    return f"CREATE superadmin: {username} / {email}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal production bootstrap for HelpChain.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if args.commit == args.dry_run:
        print("ERROR: use exactly one mode: --dry-run or --commit")
        return 2

    dry_run = args.dry_run

    with app.app_context():
        print(f"DB={app.config.get('SQLALCHEMY_DATABASE_URI')}")
        print(f"MODE={'DRY-RUN' if dry_run else 'COMMIT'}")

        messages = []

        for item in STRUCTURES:
            messages.append(upsert_structure(item["name"], item["slug"], dry_run))

        if not dry_run:
            db.session.flush()

        messages.append(ensure_superadmin(dry_run))

        for msg in messages:
            print(msg)

        if dry_run:
            db.session.rollback()
            print("DONE dry-run. No DB changes.")
        else:
            db.session.commit()
            print("DONE commit.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())