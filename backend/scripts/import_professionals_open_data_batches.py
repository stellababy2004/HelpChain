"""
Batch importer for Annuaire Sante / open extracts (no scraping).

Batches:
- Batch 1: Paris + professions (psychologue, medecin generaliste, infirmier, psychiatre)
- Batch 2: Boulogne-Billancourt, Suresnes, Issy-les-Moulineaux, Neuilly-sur-Seine
- Batch 3: FINESS structures for social / medico-social coverage

Usage (PowerShell):
  python backend/scripts/import_professionals_open_data_batches.py --batch 1 --annuaire-file data/annuaire_extract.csv --dry-run
  python backend/scripts/import_professionals_open_data_batches.py --batch 2 --annuaire-file data/annuaire_extract.csv --commit --confirm-canonical-db
  python backend/scripts/import_professionals_open_data_batches.py --batch 3 --finess-file data/finess_extract.csv --commit --confirm-canonical-db
  python backend/scripts/import_professionals_open_data_batches.py --batch all --annuaire-file data/annuaire_extract.csv --finess-file data/finess_extract.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, text

# Ensure repo root and backend package are importable when executed directly.
_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_backend_dir = os.path.abspath(os.path.join(_repo_root, "backend"))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.appy import app
from backend.extensions import db
from backend.helpchain_backend.src.models import ProfessionalLead
from backend.helpchain_backend.src.services.geocoding import geocode_location_best_effort
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)

BATCH1_PROFESSIONS = [
    "psychologue",
    "medecin generaliste",
    "infirmier",
    "psychiatre",
]
BATCH1_CITY = "paris"
BATCH2_CITIES = [
    "boulogne-billancourt",
    "suresnes",
    "issy-les-moulineaux",
    "neuilly-sur-seine",
]
BATCH3_KEYWORDS = ["social", "medico-social", "medicosocial", "médico-social"]


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def _fold(value: str | None) -> str:
    txt = _norm_lower(value)
    if not txt:
        return ""
    txt = "".join(ch for ch in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(ch))
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _norm_email(value: str | None) -> str:
    return _norm_lower(value)


def _norm_phone(value: str | None) -> str | None:
    v = _norm(value)
    return v or None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        n = float(str(value).strip().replace(",", "."))
        return n
    except Exception:
        return None


def _has_lat_lng(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def _synthetic_email(full_name: str, city: str, profession: str) -> str:
    key = f"{_fold(full_name)}|{_fold(city)}|{_fold(profession)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return f"no-email+{digest}@open-data.local"


def _normalize_headers(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (row or {}).items():
        if k is None:
            continue
        nk = _fold(str(k)).replace(" ", "_")
        out[nk] = _norm(str(v) if v is not None else "")
    return out


def _pick(rec: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in rec:
            v = _norm(str(rec.get(key) or ""))
            if v:
                return v
    return ""


def _read_csv_like(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t,")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ","
        reader = csv.DictReader(f, delimiter=delimiter)
        return [_normalize_headers(row) for row in reader]


def _normalize_row(row: dict[str, Any], source: str) -> dict[str, Any]:
    rec = _normalize_headers(row)
    full_name = _pick(rec, "full_name", "name", "nom_complet")
    if not full_name:
        first = _pick(rec, "first_name", "prenom", "given_name", "given")
        last = _pick(rec, "last_name", "nom", "family_name", "family")
        full_name = _norm(" ".join(v for v in (first, last) if v))

    profession = _pick(
        rec,
        "profession",
        "category",
        "libelle_profession",
        "profession_libelle",
        "specialite",
        "finess_categ_lib",
        "categetab",
    )
    city = _pick(rec, "city", "ville", "commune", "libelle_commune", "commune_nom")
    organization = _pick(
        rec,
        "organization",
        "organisation",
        "nom_etablissement",
        "raison_sociale",
        "etablissement",
        "structure",
    )
    email = _norm_email(_pick(rec, "email", "mail", "courriel"))
    phone = _norm_phone(_pick(rec, "phone", "telephone", "tel", "numero_telephone"))
    source_url = _pick(rec, "source_url", "url", "record_url", "fiche_url")
    address = _pick(rec, "address", "adresse", "address_line")
    lat = _to_float(_pick(rec, "latitude", "lat", "coord_lat", "y"))
    lng = _to_float(_pick(rec, "longitude", "lng", "lon", "coord_lon", "x"))

    if source == "finess_open_data" and not profession:
        profession = "Structure medico-sociale"
    if source == "finess_open_data" and not full_name and organization:
        full_name = organization

    return {
        "full_name": full_name or None,
        "email": email or None,
        "phone": phone,
        "profession": profession or None,
        "city": city or None,
        "organization": organization or None,
        "source": source,
        "source_url": source_url or None,
        "status": "imported",
        "latitude": lat if _has_lat_lng(lat, lng) else None,
        "longitude": lng if _has_lat_lng(lat, lng) else None,
        "address_for_geocode": address or None,
    }


def _is_batch1(row: dict[str, Any]) -> bool:
    city = _fold(row.get("city"))
    profession = _fold(row.get("profession"))
    if BATCH1_CITY not in city:
        return False
    return any(keyword in profession for keyword in BATCH1_PROFESSIONS)


def _is_batch2(row: dict[str, Any]) -> bool:
    city = _fold(row.get("city"))
    return any(target in city for target in BATCH2_CITIES)


def _is_batch3(row: dict[str, Any]) -> bool:
    combined = _fold(
        " ".join(
            [
                _norm(row.get("profession")),
                _norm(row.get("organization")),
                _norm(row.get("full_name")),
            ]
        )
    )
    return any(k in combined for k in BATCH3_KEYWORDS)


def _import_rows(
    *,
    rows: list[dict[str, Any]],
    batch_name: str,
    limit: int,
    dry_run: bool,
    has_source_url: bool,
    has_import_batch: bool,
    has_lat: bool,
    has_lng: bool,
    import_batch: str,
) -> tuple[int, int, int, int]:
    scanned = 0
    imported = 0
    skipped = 0
    failed = 0

    seen_email: set[str] = set()
    seen_identity: set[tuple[str, str, str]] = set()

    for row in rows:
        if imported >= limit:
            break
        scanned += 1
        try:
            full_name = _norm(row.get("full_name"))
            profession = _norm(row.get("profession"))
            city = _norm(row.get("city"))
            email = _norm_email(row.get("email"))

            if not (full_name and profession and city):
                skipped += 1
                continue

            identity_key = (_fold(full_name), _fold(city), _fold(profession))

            if email:
                if email in seen_email:
                    skipped += 1
                    continue
                seen_email.add(email)
            else:
                if identity_key in seen_identity:
                    skipped += 1
                    continue
                seen_identity.add(identity_key)

            if email:
                existing = (
                    ProfessionalLead.query.filter(func.lower(ProfessionalLead.email) == email)
                    .order_by(ProfessionalLead.id.desc())
                    .first()
                )
            else:
                existing = (
                    ProfessionalLead.query.filter(
                        func.lower(ProfessionalLead.full_name) == identity_key[0],
                        func.lower(ProfessionalLead.city) == identity_key[1],
                        func.lower(ProfessionalLead.profession) == identity_key[2],
                    )
                    .order_by(ProfessionalLead.id.desc())
                    .first()
                )
            if existing:
                skipped += 1
                continue

            lat = row.get("latitude")
            lng = row.get("longitude")
            if has_lat and has_lng and not _has_lat_lng(lat, lng):
                lat, lng = geocode_location_best_effort(
                    location_text=_norm(row.get("address_for_geocode")) or None,
                    city=city,
                )

            email_to_store = email or _synthetic_email(full_name=full_name, city=city, profession=profession)

            if dry_run:
                imported += 1
                continue

            lead = ProfessionalLead(
                full_name=full_name,
                email=email_to_store,
                phone=_norm_phone(row.get("phone")),
                profession=profession,
                city=city,
                organization=_norm(row.get("organization")) or None,
                source=_norm(row.get("source")) or "open_data_batch",
                status="imported",
                notes=f"Imported via open-data batch adapter ({batch_name})",
                created_at=datetime.now(UTC),
            )
            db.session.add(lead)
            db.session.flush()

            extra_updates: dict[str, object] = {}
            if has_source_url and row.get("source_url"):
                source_url = _norm(row.get("source_url"))
                if hasattr(lead, "source_url"):
                    setattr(lead, "source_url", source_url)
                else:
                    extra_updates["source_url"] = source_url
            if has_import_batch:
                if hasattr(lead, "import_batch"):
                    setattr(lead, "import_batch", import_batch)
                else:
                    extra_updates["import_batch"] = import_batch
            if has_lat and has_lng and _has_lat_lng(lat, lng):
                if hasattr(lead, "latitude") and hasattr(lead, "longitude"):
                    setattr(lead, "latitude", float(lat))
                    setattr(lead, "longitude", float(lng))
                else:
                    extra_updates["latitude"] = float(lat)
                    extra_updates["longitude"] = float(lng)

            if extra_updates:
                set_clause = ", ".join(f"{col} = :{col}" for col in extra_updates.keys())
                params = dict(extra_updates)
                params["id"] = int(lead.id)
                db.session.execute(
                    text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
                    params,
                )

            imported += 1
        except Exception:
            failed += 1

    return scanned, imported, skipped, failed


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch import from Annuaire/FINESS open extracts.")
    parser.add_argument("--batch", choices=("1", "2", "3", "all"), default="all")
    parser.add_argument("--annuaire-file", default="", help="Path to Annuaire/RPPS open extract file.")
    parser.add_argument("--finess-file", default="", help="Path to FINESS open extract file.")
    parser.add_argument("--limit", type=int, default=1000, help="Max imports per selected batch.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only.")
    parser.add_argument("--commit", action="store_true", help="Apply DB writes.")
    parser.add_argument("--confirm-canonical-db", action="store_true")
    args = parser.parse_args(argv)

    if args.commit and args.dry_run:
        print("WARNING: both --commit and --dry-run provided; using --commit.")
    dry_run = not args.commit
    if args.dry_run and not args.commit:
        dry_run = True

    run_batches = [args.batch] if args.batch != "all" else ["1", "2", "3"]

    annuaire_rows: list[dict[str, Any]] = []
    finess_rows: list[dict[str, Any]] = []

    if "1" in run_batches or "2" in run_batches:
        if not args.annuaire_file:
            print("ERROR: --annuaire-file is required for batch 1/2.")
            return 2
        path = Path(args.annuaire_file)
        if not path.exists() or not path.is_file():
            print(f"ERROR: annuaire file not found: {path}")
            return 2
        annuaire_rows = [_normalize_row(r, "annuaire_sante_open_extract") for r in _read_csv_like(path)]

    if "3" in run_batches:
        if not args.finess_file:
            print("ERROR: --finess-file is required for batch 3.")
            return 2
        path = Path(args.finess_file)
        if not path.exists() or not path.is_file():
            print(f"ERROR: FINESS file not found: {path}")
            return 2
        finess_rows = [_normalize_row(r, "finess_open_data") for r in _read_csv_like(path)]

    import_batch = datetime.now(UTC).strftime("open_batch_%Y%m%dT%H%M%SZ")

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 3
        if (not dry_run) and (not args.confirm_canonical_db):
            print(canonical_confirmation_error())
            return 3

        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        if "professional_leads" not in table_names:
            print("ERROR: professional_leads table is missing.")
            return 4
        columns = {c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")}
        has_source_url = "source_url" in columns
        has_import_batch = "import_batch" in columns
        has_lat = "latitude" in columns
        has_lng = "longitude" in columns

        total_scanned = 0
        total_imported = 0
        total_skipped = 0
        total_failed = 0

        for batch_no in run_batches:
            if batch_no == "1":
                rows = [r for r in annuaire_rows if _is_batch1(r)]
            elif batch_no == "2":
                rows = [r for r in annuaire_rows if _is_batch2(r)]
            else:
                rows = [r for r in finess_rows if _is_batch3(r)]

            scanned, imported, skipped, failed = _import_rows(
                rows=rows,
                batch_name=f"batch_{batch_no}",
                limit=max(1, int(args.limit or 1000)),
                dry_run=dry_run,
                has_source_url=has_source_url,
                has_import_batch=has_import_batch,
                has_lat=has_lat,
                has_lng=has_lng,
                import_batch=import_batch,
            )
            total_scanned += scanned
            total_imported += imported
            total_skipped += skipped
            total_failed += failed
            print(
                f"[{'DRY-RUN' if dry_run else 'COMMIT'}] batch={batch_no} "
                f"scanned={scanned} imported={imported} skipped={skipped} failed={failed}"
            )

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    print(
        f"[{'DRY-RUN' if dry_run else 'COMMIT'}] total "
        f"scanned={total_scanned} imported={total_imported} skipped={total_skipped} failed={total_failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
