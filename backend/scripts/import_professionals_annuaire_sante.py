"""
Import professional leads from the official Annuaire Sante FHIR API.

Usage (PowerShell):
  python backend/scripts/import_professionals_annuaire_sante.py --city Paris --limit 50 --dry-run
  python backend/scripts/import_professionals_annuaire_sante.py --city Paris --profession Medecin --limit 50 --commit --confirm-canonical-db
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime
from typing import Any

import requests
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


ANNUAIRE_BASE_URL = os.getenv(
    "ANNUAIRE_SANTE_FHIR_BASE_URL",
    "https://gateway.api.esante.gouv.fr/fhir/v2",
).rstrip("/")
ANNUAIRE_API_KEY = os.getenv("ANNUAIRE_SANTE_API_KEY", "").strip() or os.getenv(
    "ESANTE_API_KEY", ""
).strip()
ANNUAIRE_BEARER_TOKEN = os.getenv("ANNUAIRE_SANTE_BEARER_TOKEN", "").strip()
SOURCE_NAME = "annuaire_sante"


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def _clean_phone(value: str | None) -> str | None:
    phone = _norm(value)
    return phone or None


def _collect_telecom(
    *resources: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    email = None
    phone = None
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        for telecom in resource.get("telecom") or []:
            if not isinstance(telecom, dict):
                continue
            system = _norm_lower(telecom.get("system"))
            value = _norm(telecom.get("value"))
            if not value:
                continue
            if system == "email" and email is None:
                email = value.lower()
            elif system == "phone" and phone is None:
                phone = value
            if email and phone:
                return email, _clean_phone(phone)
    return (email.lower() if email else None), _clean_phone(phone)


def _extract_name(practitioner: dict[str, Any] | None) -> str | None:
    if not isinstance(practitioner, dict):
        return None
    for name in practitioner.get("name") or []:
        if not isinstance(name, dict):
            continue
        text_name = _norm(name.get("text"))
        if text_name:
            return text_name
        prefix = " ".join(_norm(p) for p in (name.get("prefix") or []) if _norm(p))
        given = " ".join(_norm(g) for g in (name.get("given") or []) if _norm(g))
        family = _norm(name.get("family"))
        combined = " ".join(v for v in (prefix, given, family) if v)
        if combined:
            return combined
    return None


def _extract_profession(
    role: dict[str, Any] | None,
    practitioner: dict[str, Any] | None,
    profession_hint: str | None = None,
    category_hint: str | None = None,
) -> str:
    role_codings = []
    if isinstance(role, dict):
        for code in role.get("code") or []:
            if not isinstance(code, dict):
                continue
            text_label = _norm(code.get("text"))
            if text_label:
                role_codings.append(text_label)
            for coding in code.get("coding") or []:
                if not isinstance(coding, dict):
                    continue
                display = _norm(coding.get("display"))
                code_val = _norm(coding.get("code"))
                if display:
                    role_codings.append(display)
                elif code_val:
                    role_codings.append(code_val)
    if role_codings:
        return role_codings[0]

    if isinstance(practitioner, dict):
        for qualification in practitioner.get("qualification") or []:
            if not isinstance(qualification, dict):
                continue
            concept = qualification.get("code") or {}
            if isinstance(concept, dict):
                text_label = _norm(concept.get("text"))
                if text_label:
                    return text_label
                for coding in concept.get("coding") or []:
                    if not isinstance(coding, dict):
                        continue
                    display = _norm(coding.get("display"))
                    code_val = _norm(coding.get("code"))
                    if display:
                        return display
                    if code_val:
                        return code_val

    if profession_hint:
        return profession_hint
    if category_hint:
        return category_hint
    return "Professionnel de sante"


def _extract_org_city_and_address(
    organization: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not isinstance(organization, dict):
        return None, None
    for address in organization.get("address") or []:
        if not isinstance(address, dict):
            continue
        city = _norm(address.get("city")) or None
        parts: list[str] = []
        for line in address.get("line") or []:
            line_txt = _norm(line)
            if line_txt:
                parts.append(line_txt)
        postal = _norm(address.get("postalCode"))
        country = _norm(address.get("country"))
        if city:
            parts.append(city)
        if postal:
            parts.append(postal)
        if country:
            parts.append(country)
        full_address = ", ".join(parts) if parts else None
        return city, full_address
    return None, None


def _resource_id(resource: dict[str, Any]) -> str | None:
    rid = _norm(resource.get("id"))
    if rid:
        return rid
    ref = _norm(resource.get("fullUrl"))
    if not ref:
        return None
    if "/" in ref:
        return ref.rsplit("/", 1)[-1]
    return ref or None


def _ref_to_id(reference: str | None) -> str | None:
    raw = _norm(reference)
    if not raw:
        return None
    if "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw


def _bundle_entries(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        return []
    out: list[dict[str, Any]] = []
    for item in entries:
        if isinstance(item, dict):
            out.append(item)
    return out


def _next_link(bundle: dict[str, Any]) -> str | None:
    links = bundle.get("link")
    if not isinstance(links, list):
        return None
    for item in links:
        if not isinstance(item, dict):
            continue
        if _norm_lower(item.get("relation")) == "next":
            return _norm(item.get("url")) or None
    return None


def _fhir_headers() -> dict[str, str]:
    if not ANNUAIRE_API_KEY:
        raise ValueError(
            "ANNUAIRE_SANTE_API_KEY is required. Obtain it via ANS/Gravitee and set the env var."
        )
    headers = {
        "ESANTE-API-KEY": ANNUAIRE_API_KEY,
        "Accept": "application/fhir+json, application/json",
    }
    if ANNUAIRE_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {ANNUAIRE_BEARER_TOKEN}"
    return headers


def _fetch_fhir_pages(
    *,
    city: str,
    profession: str | None,
    category: str | None,
    limit: int,
    timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    session = requests.Session()
    headers = _fhir_headers()

    base = f"{ANNUAIRE_BASE_URL}/PractitionerRole"
    # Use chained organization filter for city and include referenced resources.
    params: dict[str, str] = {
        "active": "true",
        "organization.address-city": city,
        "_count": str(min(max(limit, 1), 100)),
        "_include": "PractitionerRole:practitioner,PractitionerRole:organization",
    }
    if profession:
        params["role:text"] = profession
    elif category:
        params["role:text"] = category

    bundles: list[dict[str, Any]] = []
    next_url: str | None = base
    next_params: dict[str, str] | None = params

    while next_url and len(bundles) < max(limit, 1):
        resp = session.get(
            next_url,
            params=next_params,
            headers=headers,
            timeout=timeout_seconds,
        )
        if not resp.ok:
            preview = (resp.text or "")[:200].replace("\n", " ").strip()
            raise RuntimeError(
                f"FHIR request failed ({resp.status_code}) at {resp.url}: {preview}"
            )
        bundle = resp.json() or {}
        if not isinstance(bundle, dict):
            raise RuntimeError(f"Unexpected non-object FHIR payload from {resp.url}")
        bundles.append(bundle)
        if len(bundles) >= max(limit, 1):
            break
        next_url = _next_link(bundle)
        next_params = None
    return bundles


def _normalize_candidates(
    *,
    bundles: list[dict[str, Any]],
    city_filter: str,
    profession_filter: str | None,
    category_filter: str | None,
    hard_limit: int,
) -> list[dict[str, Any]]:
    city_filter_norm = _norm_lower(city_filter)
    profession_filter_norm = _norm_lower(profession_filter)
    category_filter_norm = _norm_lower(category_filter)

    practitioners: dict[str, dict[str, Any]] = {}
    organizations: dict[str, dict[str, Any]] = {}
    roles: list[dict[str, Any]] = []

    for bundle in bundles:
        for entry in _bundle_entries(bundle):
            resource = entry.get("resource")
            if not isinstance(resource, dict):
                continue
            rtype = _norm(resource.get("resourceType"))
            rid = _resource_id(resource)
            if rtype == "Practitioner" and rid:
                practitioners[rid] = resource
            elif rtype == "Organization" and rid:
                organizations[rid] = resource
            elif rtype == "PractitionerRole":
                roles.append(resource)

    out: list[dict[str, Any]] = []
    for role in roles:
        practitioner_id = _ref_to_id((role.get("practitioner") or {}).get("reference"))
        organization_id = _ref_to_id((role.get("organization") or {}).get("reference"))
        practitioner = practitioners.get(practitioner_id or "")
        organization = organizations.get(organization_id or "")

        full_name = _extract_name(practitioner)
        org_name = _norm((organization or {}).get("name")) or None
        city, full_address = _extract_org_city_and_address(organization)
        profession = _extract_profession(
            role=role,
            practitioner=practitioner,
            profession_hint=profession_filter,
            category_hint=category_filter,
        )
        email, phone = _collect_telecom(practitioner, role, organization)

        city_norm = _norm_lower(city)
        if city_filter_norm and city_norm and city_filter_norm not in city_norm:
            continue
        prof_norm = _norm_lower(profession)
        if profession_filter_norm and profession_filter_norm not in prof_norm:
            continue
        if category_filter_norm and category_filter_norm not in prof_norm:
            continue
        if not (full_name and city and profession):
            continue

        role_id = _resource_id(role)
        source_url = (
            f"{ANNUAIRE_BASE_URL}/PractitionerRole/{role_id}" if role_id else ANNUAIRE_BASE_URL
        )
        out.append(
            {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "profession": profession,
                "city": city,
                "organization": org_name,
                "source": SOURCE_NAME,
                "source_url": source_url,
                "status": "imported",
                "address_for_geocode": full_address,
            }
        )
        if len(out) >= hard_limit:
            break
    return out


def _synthetic_email(full_name: str, city: str, profession: str) -> str:
    base = f"{_norm_lower(full_name)}|{_norm_lower(city)}|{_norm_lower(profession)}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:20]
    return f"no-email+{digest}@annuaire-sante.local"


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import professional leads from official Annuaire Sante FHIR API."
    )
    parser.add_argument("--city", default="Paris", help="City filter (example: Paris).")
    parser.add_argument("--profession", default="", help="Profession free-text filter.")
    parser.add_argument("--category", default="", help="Category free-text filter.")
    parser.add_argument("--limit", type=int, default=50, help="Max records to import.")
    parser.add_argument("--commit", action="store_true", help="Apply DB writes.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only.")
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

    city = _norm(args.city) or "Paris"
    profession = _norm(args.profession) or None
    category = _norm(args.category) or None
    hard_limit = max(1, int(args.limit or 50))

    scanned = 0
    imported = 0
    skipped = 0
    failed = 0

    try:
        bundles = _fetch_fhir_pages(
            city=city,
            profession=profession,
            category=category,
            limit=hard_limit,
        )
    except Exception as exc:
        print(f"ERROR: failed to fetch Annuaire Sante FHIR data: {exc}")
        return 2

    candidates = _normalize_candidates(
        bundles=bundles,
        city_filter=city,
        profession_filter=profession,
        category_filter=category,
        hard_limit=hard_limit,
    )

    batch_id = datetime.now(UTC).strftime("annuaire_%Y%m%dT%H%M%SZ")

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
        seen_tuple: set[tuple[str, str, str]] = set()

        for candidate in candidates:
            scanned += 1
            full_name = _norm(candidate.get("full_name"))
            profession_val = _norm(candidate.get("profession"))
            city_val = _norm(candidate.get("city"))
            if not (full_name and profession_val and city_val):
                skipped += 1
                continue

            tuple_key = (_norm_lower(full_name), _norm_lower(city_val), _norm_lower(profession_val))
            email_public = _norm_lower(candidate.get("email")) or None

            if email_public:
                if email_public in seen_email:
                    skipped += 1
                    continue
                seen_email.add(email_public)
            else:
                if tuple_key in seen_tuple:
                    skipped += 1
                    continue
                seen_tuple.add(tuple_key)

            try:
                if email_public:
                    existing = (
                        ProfessionalLead.query.filter(
                            func.lower(ProfessionalLead.email) == email_public
                        )
                        .order_by(ProfessionalLead.id.desc())
                        .first()
                    )
                else:
                    existing = (
                        ProfessionalLead.query.filter(
                            func.lower(ProfessionalLead.full_name) == tuple_key[0],
                            func.lower(ProfessionalLead.city) == tuple_key[1],
                            func.lower(ProfessionalLead.profession) == tuple_key[2],
                        )
                        .order_by(ProfessionalLead.id.desc())
                        .first()
                    )
                if existing:
                    skipped += 1
                    continue

                lat = None
                lng = None
                if has_lat and has_lng:
                    lat, lng = geocode_location_best_effort(
                        location_text=_norm(candidate.get("address_for_geocode")) or None,
                        city=city_val,
                    )

                email_to_store = email_public or _synthetic_email(
                    full_name=full_name,
                    city=city_val,
                    profession=profession_val,
                )

                if dry_run:
                    print(
                        f"DRY-RUN create: {full_name} | {profession_val} | {city_val} | {email_to_store}"
                    )
                    imported += 1
                    continue

                with db.session.begin_nested():
                    lead = ProfessionalLead(
                        email=email_to_store,
                        full_name=full_name,
                        phone=_clean_phone(candidate.get("phone")),
                        city=city_val,
                        profession=profession_val,
                        organization=_norm(candidate.get("organization")) or None,
                        source=SOURCE_NAME,
                        status="imported",
                        notes="Imported from Annuaire Sante FHIR API",
                        created_at=datetime.now(UTC),
                    )
                    db.session.add(lead)
                    db.session.flush()

                    extra_updates: dict[str, object] = {}
                    if has_source_url and candidate.get("source_url"):
                        source_url = _norm(candidate.get("source_url"))
                        if hasattr(lead, "source_url"):
                            setattr(lead, "source_url", source_url)
                        else:
                            extra_updates["source_url"] = source_url
                    if has_import_batch:
                        if hasattr(lead, "import_batch"):
                            setattr(lead, "import_batch", batch_id)
                        else:
                            extra_updates["import_batch"] = batch_id
                    if has_lat and has_lng and lat is not None and lng is not None:
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
            except Exception as exc:
                failed += 1
                print(f"ERROR candidate failed: {exc}")

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    mode = "DRY-RUN" if dry_run else "COMMIT"
    query_desc = [f"city={city}", f"limit={hard_limit}"]
    if profession:
        query_desc.append(f"profession={profession}")
    if category:
        query_desc.append(f"category={category}")
    print(
        f"[{mode}] source={SOURCE_NAME} {' '.join(query_desc)} "
        f"scanned={scanned} imported={imported} skipped={skipped} failed={failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
