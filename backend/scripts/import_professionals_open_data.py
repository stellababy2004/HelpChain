"""
Production-safe importer for official/open professional datasets.

Supports:
- CSV file
- Open dataset extracts (CSV/TSV-like with flexible headers)
- Normalized JSON files (future API/FHIR adapter outputs)

Usage (PowerShell):
  python backend/scripts/import_professionals_open_data.py --file data/professionals.csv --source-type csv --dry-run
  python backend/scripts/import_professionals_open_data.py --file data/rpps_extract.csv --source-type open_extract --city Paris --limit 100 --commit --confirm-canonical-db
  python backend/scripts/import_professionals_open_data.py --file data/normalized.json --source-type json --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
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


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def _norm_spaces_lower(value: str | None) -> str:
    return re.sub(r"\s+", " ", _norm(value)).strip().lower()


def _norm_email(value: str | None) -> str:
    return _norm_lower(value)


def _norm_phone(value: str | None) -> str | None:
    p = _norm(value)
    return p or None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        txt = str(value).strip().replace(",", ".")
        if not txt:
            return None
        n = float(txt)
        if not (-180.0 <= n <= 180.0):
            return None
        return n
    except Exception:
        return None


def _has_lat_lng(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def _synthetic_email(full_name: str, city: str, profession: str) -> str:
    key = f"{_norm_spaces_lower(full_name)}|{_norm_spaces_lower(city)}|{_norm_spaces_lower(profession)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return f"no-email+{digest}@open-data.local"


def _pick(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in record:
            v = _norm(str(record.get(key) or ""))
            if v:
                return v
    return ""


def _normalize_headers(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (row or {}).items():
        if k is None:
            continue
        nk = _norm_spaces_lower(str(k)).replace(" ", "_")
        out[nk] = _norm(str(v) if v is not None else "")
    return out


def _read_csv_like(path: Path, delimiter: str | None = None) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        if delimiter is None:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t,")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","
        reader = csv.DictReader(f, delimiter=delimiter)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append(_normalize_headers(row))
        return rows


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "records", "data", "leads", "results"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _infer_source_default(source_type: str) -> str:
    if source_type == "open_extract":
        return "open_data_extract"
    if source_type == "json":
        return "json_import"
    return "csv_import"


def _normalize_row(row: dict[str, Any], source_type: str) -> dict[str, Any]:
    rec = _normalize_headers(row)

    full_name = _pick(rec, "full_name", "name", "nom_complet")
    if not full_name:
        first = _pick(rec, "first_name", "prenom", "given_name", "given")
        last = _pick(rec, "last_name", "nom", "family_name", "family")
        full_name = _norm(" ".join(x for x in (first, last) if x))

    profession = _pick(
        rec,
        "profession",
        "category",
        "profession_label",
        "libelle_profession",
        "profession_libelle",
        "specialite",
        "finess_categ_lib",
    )
    city = _pick(rec, "city", "ville", "commune", "libelle_commune", "commune_nom")
    organization = _pick(
        rec,
        "organization",
        "organisation",
        "structure",
        "raison_sociale",
        "nom_etablissement",
        "etablissement",
    )
    email = _norm_email(_pick(rec, "email", "mail", "courriel"))
    phone = _norm_phone(_pick(rec, "phone", "telephone", "tel", "numero_telephone"))
    source = _pick(rec, "source") or _infer_source_default(source_type)
    source_url = _pick(
        rec,
        "source_url",
        "url",
        "record_url",
        "fiche_url",
    )
    lat = _to_float(_pick(rec, "latitude", "lat", "coord_lat", "y"))
    lng = _to_float(_pick(rec, "longitude", "lng", "lon", "coord_lon", "x"))
    address = _pick(rec, "address", "adresse", "address_line")

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


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import professionals from official/open data files.")
    parser.add_argument("--file", required=True, help="Input file path.")
    parser.add_argument(
        "--source-type",
        required=True,
        choices=("csv", "json", "open_extract"),
        help="Input type: csv|json|open_extract.",
    )
    parser.add_argument("--city", default="Paris", help="Optional city filter.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to import.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only.")
    parser.add_argument("--commit", action="store_true", help="Apply DB writes.")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag when using --commit.",
    )
    args = parser.parse_args(argv)

    if args.commit and args.dry_run:
        print("WARNING: both --commit and --dry-run provided; using --commit.")
    dry_run = not args.commit
    if args.dry_run and not args.commit:
        dry_run = True

    file_path = Path(args.file)
    if not file_path.exists() or not file_path.is_file():
        print(f"ERROR: input file not found: {file_path}")
        return 2

    try:
        if args.source_type == "json":
            raw_rows = _read_json(file_path)
        elif args.source_type == "open_extract":
            raw_rows = _read_csv_like(file_path, delimiter=None)
        else:
            raw_rows = _read_csv_like(file_path, delimiter=",")
    except Exception as exc:
        print(f"ERROR: failed to read input: {exc}")
        return 2

    city_filter = _norm_spaces_lower(args.city)
    hard_limit = max(1, int(args.limit or 100))
    batch_id = datetime.now(UTC).strftime("open_data_%Y%m%dT%H%M%SZ")

    scanned = 0
    imported = 0
    skipped = 0
    failed = 0

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

        columns = {
            c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")
        }
        has_source_url = "source_url" in columns
        has_import_batch = "import_batch" in columns
        has_lat = "latitude" in columns
        has_lng = "longitude" in columns

        seen_email: set[str] = set()
        seen_identity: set[tuple[str, str, str]] = set()

        for row in raw_rows:
            if imported >= hard_limit:
                break
            scanned += 1
            try:
                norm = _normalize_row(row, args.source_type)
                full_name = _norm(norm.get("full_name"))
                profession = _norm(norm.get("profession"))
                city = _norm(norm.get("city"))
                email = _norm_email(norm.get("email"))

                if not (full_name and profession and city):
                    skipped += 1
                    continue

                if city_filter and city_filter not in _norm_spaces_lower(city):
                    skipped += 1
                    continue

                identity_key = (
                    _norm_spaces_lower(full_name),
                    _norm_spaces_lower(city),
                    _norm_spaces_lower(profession),
                )

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

                lat = norm.get("latitude")
                lng = norm.get("longitude")
                if has_lat and has_lng and not _has_lat_lng(lat, lng):
                    lat, lng = geocode_location_best_effort(
                        location_text=_norm(norm.get("address_for_geocode")) or None,
                        city=city,
                    )

                email_to_store = email or _synthetic_email(
                    full_name=full_name,
                    city=city,
                    profession=profession,
                )

                if dry_run:
                    imported += 1
                    continue

                lead = ProfessionalLead(
                    full_name=full_name,
                    email=email_to_store,
                    phone=_norm_phone(norm.get("phone")),
                    profession=profession,
                    city=city,
                    organization=_norm(norm.get("organization")) or None,
                    source=_norm(norm.get("source")) or _infer_source_default(args.source_type),
                    status="imported",
                    notes=f"Imported via open-data adapter ({args.source_type})",
                    created_at=datetime.now(UTC),
                )
                db.session.add(lead)
                db.session.flush()

                extra_updates: dict[str, object] = {}
                if has_source_url and norm.get("source_url"):
                    if hasattr(lead, "source_url"):
                        setattr(lead, "source_url", _norm(norm.get("source_url")))
                    else:
                        extra_updates["source_url"] = _norm(norm.get("source_url"))
                if has_import_batch:
                    if hasattr(lead, "import_batch"):
                        setattr(lead, "import_batch", batch_id)
                    else:
                        extra_updates["import_batch"] = batch_id
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

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    mode = "DRY-RUN" if dry_run else "COMMIT"
    print(
        f"[{mode}] source_type={args.source_type} file={file_path} city={args.city} limit={hard_limit} "
        f"scanned={scanned} imported={imported} skipped={skipped} failed={failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
