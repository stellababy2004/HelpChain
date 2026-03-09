#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.appy import app
from backend.extensions import db
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)
from backend.models import Structure, StructureService

DEMO_STRUCTURE_NAME = "CCAS Boulogne-Billancourt"
DEMO_STRUCTURE_SLUG = "ccas-boulogne-billancourt"

DEMO_SERVICES = [
    ("accueil_social", "Accueil social"),
    ("hebergement_logement", "Hebergement / Logement"),
    ("aide_alimentaire", "Aide alimentaire"),
    ("seniors_isolement", "Seniors / Isolement"),
    ("acces_aux_droits", "Acces aux droits"),
    ("protection_violences", "Protection / Violences"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed demo structure and services for internal request routing."
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag. Refuses writes without explicit confirmation.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print_app_db_preflight(db_uri)

        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2

        if not is_canonical_db_uri(db_uri):
            print(canonical_mismatch_error(db_uri))
            return 2

        tables = set(inspect(db.engine).get_table_names())
        required_tables = {"structures", "structure_services"}
        missing = sorted(required_tables - tables)
        if missing:
            print(f"ERROR: required table(s) missing: {', '.join(missing)}")
            print("HINT: run canonical migrations before seeding services.")
            return 1

        structure = Structure.query.filter_by(slug=DEMO_STRUCTURE_SLUG).first()
        structure_created = False
        if structure is None:
            structure = Structure(name=DEMO_STRUCTURE_NAME, slug=DEMO_STRUCTURE_SLUG)
            db.session.add(structure)
            db.session.flush()
            structure_created = True
        elif structure.name != DEMO_STRUCTURE_NAME:
            structure.name = DEMO_STRUCTURE_NAME

        created = 0
        updated = 0
        for code, name in DEMO_SERVICES:
            service = StructureService.query.filter_by(
                structure_id=structure.id,
                code=code,
            ).first()
            if service is None:
                db.session.add(
                    StructureService(
                        structure_id=structure.id,
                        code=code,
                        name=name,
                        is_active=True,
                    )
                )
                created += 1
                continue

            changed = False
            if service.name != name:
                service.name = name
                changed = True
            if not bool(service.is_active):
                service.is_active = True
                changed = True
            if changed:
                updated += 1

        db.session.commit()

        print(f"STRUCTURE: {structure.name} (slug={structure.slug}, id={structure.id})")
        print(f"STRUCTURE_CREATED: {'yes' if structure_created else 'no'}")
        print(f"SERVICES_CREATED: {created}")
        print(f"SERVICES_UPDATED: {updated}")
        print(
            "SERVICES_TOTAL:",
            StructureService.query.filter_by(structure_id=structure.id).count(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
