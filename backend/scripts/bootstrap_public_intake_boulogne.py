from __future__ import annotations

import argparse

from backend.appy import app
from backend.extensions import db
from backend.models import Structure, StructureCoverageArea, StructureService


STRUCTURE_NAME = "CCAS Boulogne-Billancourt"
STRUCTURE_SLUG = "ccas-boulogne-billancourt"

COVERAGE_TYPE = "commune"
COVERAGE_NAME = "Boulogne-Billancourt"
POSTAL_CODE = "92100"

SERVICES = (
    ("food", "Aide alimentaire"),
    ("admin", "Accompagnement administratif"),
    ("housing", "Logement et hebergement"),
    ("legal", "Acces aux droits"),
    ("health", "Coordination sante"),
    ("orientation", "Orientation partenaire"),
)


def ensure_structure(messages: list[str]) -> Structure:
    structure = Structure.query.filter_by(slug=STRUCTURE_SLUG).first()

    if structure is None:
        structure = Structure(
            name=STRUCTURE_NAME,
            slug=STRUCTURE_SLUG,
            status="active",
        )
        db.session.add(structure)
        db.session.flush()
        messages.append(f"CREATE structure: {STRUCTURE_NAME}")
    else:
        messages.append(
            f"FOUND structure: id={structure.id} name={structure.name!r}"
        )

    if structure.name != STRUCTURE_NAME:
        messages.append(
            f"UPDATE structure name: {structure.name!r} -> {STRUCTURE_NAME!r}"
        )
        structure.name = STRUCTURE_NAME

    if structure.status != "active":
        messages.append(
            f"UPDATE structure status: {structure.status!r} -> 'active'"
        )
        structure.status = "active"

    return structure


def ensure_coverage(
    structure: Structure,
    messages: list[str],
) -> StructureCoverageArea:
    coverage = StructureCoverageArea.query.filter_by(
        structure_id=structure.id,
        area_type=COVERAGE_TYPE,
        name=COVERAGE_NAME,
    ).first()

    if coverage is None:
        coverage = StructureCoverageArea(
            structure_id=structure.id,
            area_type=COVERAGE_TYPE,
            name=COVERAGE_NAME,
            postal_code=POSTAL_CODE,
            is_active=True,
        )
        db.session.add(coverage)
        messages.append(
            f"CREATE coverage: {COVERAGE_NAME} / {POSTAL_CODE}"
        )
    else:
        messages.append(
            f"FOUND coverage: id={coverage.id} "
            f"name={coverage.name!r} postal_code={coverage.postal_code!r}"
        )

        if coverage.postal_code != POSTAL_CODE:
            messages.append(
                f"UPDATE coverage postal_code: "
                f"{coverage.postal_code!r} -> {POSTAL_CODE!r}"
            )
            coverage.postal_code = POSTAL_CODE

        if not coverage.is_active:
            messages.append("UPDATE coverage: activate")
            coverage.is_active = True

    return coverage


def ensure_services(
    structure: Structure,
    messages: list[str],
) -> None:
    for code, name in SERVICES:
        service = StructureService.query.filter_by(
            structure_id=structure.id,
            code=code,
        ).first()

        if service is None:
            service = StructureService(
                structure_id=structure.id,
                code=code,
                name=name,
                is_active=True,
            )
            db.session.add(service)
            messages.append(f"CREATE service: {code}")
            continue

        messages.append(
            f"FOUND service: id={service.id} code={code!r}"
        )

        if service.name != name:
            messages.append(
                f"UPDATE service {code} name: {service.name!r} -> {name!r}"
            )
            service.name = name

        if not service.is_active:
            messages.append(f"UPDATE service {code}: activate")
            service.is_active = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap Boulogne public intake routing."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if args.dry_run == args.commit:
        print("ERROR: use exactly one mode: --dry-run or --commit")
        return 2

    with app.app_context():
        messages: list[str] = []

        structure = ensure_structure(messages)
        ensure_coverage(structure, messages)
        ensure_services(structure, messages)

        db.session.flush()

        print("\n===== BOULOGNE PUBLIC INTAKE BOOTSTRAP =====")
        print(f"MODE={'DRY-RUN' if args.dry_run else 'COMMIT'}")
        print(f"STRUCTURE_ID={structure.id}")

        for message in messages:
            print(message)

        if args.dry_run:
            db.session.rollback()
            print("\nDONE dry-run. No DB changes.")
        else:
            db.session.commit()
            print("\nDONE commit.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
