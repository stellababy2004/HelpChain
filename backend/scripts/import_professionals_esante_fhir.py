from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
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
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)

FHIR_BASE_URL = "https://gateway.api.esante.gouv.fr/fhir"


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def _norm_cmp(value: str | None) -> str:
    txt = _norm_lower(value).replace("-", " ")
    return " ".join(txt.split())


def _json_compact(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _append_note(existing: str | None, fragment: str) -> str:
    base = _norm(existing)
    if not base:
        return fragment
    if fragment in base:
        return base
    return f"{base} | {fragment}"


def _synthetic_email(role_id: str | None, practitioner_name: str | None) -> str:
    seed = f"{_norm_lower(role_id)}|{_norm_lower(practitioner_name)}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]
    return f"no-email+{digest}@esante-fhir.local"


def _is_synthetic_email(email: str | None) -> bool:
    value = _norm_lower(email)
    return value.startswith("no-email+") and value.endswith("@esante-fhir.local")


def build_headers(api_key: str) -> Dict[str, str]:
    return {
        "ESANTE-API-KEY": api_key,
        "Accept": "application/fhir+json",
        "User-Agent": "HelpChain-Importer/1.0",
    }


def get_resource_id(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    if "/" not in ref:
        return ref
    return ref.split("/")[-1]


def parse_human_name(name_obj: Dict[str, Any]) -> str:
    family = name_obj.get("family", "") or ""
    given = " ".join(name_obj.get("given", []) or [])
    full = f"{given} {family}".strip()
    return full or family or given


def parse_address(address_obj: Dict[str, Any]) -> Dict[str, Optional[str]]:
    lines = address_obj.get("line", []) or []
    return {
        "line1": ", ".join(lines) if lines else None,
        "city": address_obj.get("city"),
        "postal_code": address_obj.get("postalCode"),
        "country": address_obj.get("country"),
    }


def extract_identifier(
    resource: Dict[str, Any], preferred_system_contains: Optional[str] = None
) -> Optional[str]:
    identifiers = resource.get("identifier", []) or []
    if preferred_system_contains:
        for ident in identifiers:
            system = ident.get("system", "") or ""
            if preferred_system_contains.lower() in system.lower():
                return ident.get("value")
    for ident in identifiers:
        if ident.get("value"):
            return ident["value"]
    return None


def bundle_entries(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    return bundle.get("entry", []) or []


def index_included_resources(
    bundle: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    practitioners: Dict[str, Dict[str, Any]] = {}
    organizations: Dict[str, Dict[str, Any]] = {}

    for entry in bundle_entries(bundle):
        resource = entry.get("resource", {}) or {}
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if not rid:
            continue
        if rtype == "Practitioner":
            practitioners[rid] = resource
        elif rtype == "Organization":
            organizations[rid] = resource

    return practitioners, organizations


def extract_specialties(practitioner_role: Dict[str, Any]) -> List[str]:
    specialties = []
    for spec in practitioner_role.get("specialty", []) or []:
        for coding in spec.get("coding", []) or []:
            display = coding.get("display")
            if display:
                specialties.append(display)
        text = spec.get("text")
        if text:
            specialties.append(text)

    seen = set()
    out = []
    for value in specialties:
        key = _norm_lower(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def role_to_record(
    role: Dict[str, Any],
    practitioners: Dict[str, Dict[str, Any]],
    organizations: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    practitioner_ref = get_resource_id((role.get("practitioner") or {}).get("reference"))
    organization_ref = get_resource_id((role.get("organization") or {}).get("reference"))

    practitioner = practitioners.get(practitioner_ref or "")
    organization = organizations.get(organization_ref or "")

    practitioner_name = None
    practitioner_identifier = None
    if practitioner:
        names = practitioner.get("name", []) or []
        if names:
            practitioner_name = parse_human_name(names[0])
        practitioner_identifier = extract_identifier(
            practitioner, preferred_system_contains="rpps"
        )

    org_name = None
    org_identifier = None
    org_city = None
    org_postal_code = None
    org_address_line1 = None
    if organization:
        org_name = organization.get("name")
        org_identifier = extract_identifier(organization)
        addresses = organization.get("address", []) or []
        if addresses:
            addr = parse_address(addresses[0])
            org_city = addr["city"]
            org_postal_code = addr["postal_code"]
            org_address_line1 = addr["line1"]

    telecoms = role.get("telecom", []) or []
    phone = None
    email = None
    for telecom in telecoms:
        system = telecom.get("system")
        value = telecom.get("value")
        if system == "phone" and value and not phone:
            phone = value
        elif system == "email" and value and not email:
            email = value

    return {
        "source": "esante_fhir",
        "source_resource_type": "PractitionerRole",
        "source_role_id": role.get("id"),
        "source_practitioner_id": practitioner_ref,
        "source_organization_id": organization_ref,
        "practitioner_name": practitioner_name,
        "practitioner_identifier": practitioner_identifier,
        "organization_name": org_name,
        "organization_identifier": org_identifier,
        "city": org_city,
        "postal_code": org_postal_code,
        "address_line1": org_address_line1,
        "phone": phone,
        "email": email,
        "specialties": extract_specialties(role),
        "active": role.get("active"),
    }


def fetch_bundle(
    session: requests.Session,
    headers: Dict[str, str],
    city: str,
    count: int,
    next_url: Optional[str] = None,
) -> Dict[str, Any]:
    if next_url:
        resp = session.get(next_url, headers=headers, timeout=30)
    else:
        params = [
            ("_count", str(count)),
            ("_include", "PractitionerRole:practitioner"),
            ("_include", "PractitionerRole:organization"),
        ]
        resp = session.get(
            f"{FHIR_BASE_URL}/PractitionerRole",
            headers=headers,
            params=params,
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()


def get_next_link(bundle: Dict[str, Any]) -> Optional[str]:
    for link in bundle.get("link", []) or []:
        if link.get("relation") == "next":
            return link.get("url")
    return None


def run_import(
    city: str, count: int, max_pages: int, sleep_seconds: float
) -> List[Dict[str, Any]]:
    load_dotenv()
    api_key = os.getenv("ESANTE_API_KEY")
    if not api_key:
        raise RuntimeError("ESANTE_API_KEY is missing in environment.")

    headers = build_headers(api_key)
    session = requests.Session()

    all_records: List[Dict[str, Any]] = []
    seen_role_ids = set()
    next_url = None
    page = 0

    while True:
        page += 1
        if page > max_pages:
            break

        bundle = fetch_bundle(
            session=session,
            headers=headers,
            city=city,
            count=count,
            next_url=next_url,
        )
        practitioners, organizations = index_included_resources(bundle)

        for entry in bundle_entries(bundle):
            resource = entry.get("resource", {}) or {}
            if resource.get("resourceType") != "PractitionerRole":
                continue
            role_id = resource.get("id")
            if not role_id or role_id in seen_role_ids:
                continue
            seen_role_ids.add(role_id)
            all_records.append(role_to_record(resource, practitioners, organizations))

        next_url = get_next_link(bundle)
        if not next_url:
            break
        time.sleep(sleep_seconds)

    return all_records


def normalize_fhir_record(record: dict[str, Any]) -> dict[str, Any]:
    specialties = record.get("specialties") or []
    profession = specialties[0] if specialties else "Professionnel de sante"
    source_role_id = _norm(record.get("source_role_id")) or None
    source_url = f"{FHIR_BASE_URL}/PractitionerRole/{source_role_id}" if source_role_id else None
    practitioner_name = _norm(record.get("practitioner_name")) or None
    organization_name = _norm(record.get("organization_name")) or None

    return {
        "source": "esante_fhir",
        "source_external_id": source_role_id,
        "source_url": source_url,
        "practitioner_name": practitioner_name,
        "practitioner_identifier": _norm(record.get("practitioner_identifier")) or None,
        "organization_name": organization_name,
        "organization_identifier": _norm(record.get("organization_identifier")) or None,
        "postal_code": _norm(record.get("postal_code")) or None,
        "address_line1": _norm(record.get("address_line1")) or None,
        "city": _norm(record.get("city")) or None,
        "phone": _norm(record.get("phone")) or None,
        "email": _norm_lower(record.get("email")) or None,
        "specialties": specialties,
        "profession": _norm(profession) or "Professionnel de sante",
        "active": record.get("active"),
        "full_name": practitioner_name or organization_name,
        "organization": organization_name,
        "raw": record,
    }


def matches_local_filters(
    record: dict[str, Any],
    *,
    city: str | None = None,
    postal_code: str | None = None,
    organization_name_contains: str | None = None,
    city_token_all: str | None = None,
    organization_token_all: str | None = None,
) -> bool:
    city_filter = _norm_cmp(city)
    postal_filter = _norm(postal_code)
    org_filter = _norm_cmp(organization_name_contains)
    city_tokens_all = [t for t in _norm_cmp(city_token_all).split(" ") if t]
    org_tokens_all = [t for t in _norm_cmp(organization_token_all).split(" ") if t]
    city_value = _norm_cmp(record.get("city"))
    org_value = _norm_cmp(record.get("organization_name"))

    if city_filter:
        if city_filter == "paris":
            if not city_value.startswith("paris"):
                return False
        elif city_filter not in city_value:
            return False
    if postal_filter and _norm(record.get("postal_code")) != postal_filter:
        return False
    if org_filter and org_filter not in org_value:
        return False
    if city_tokens_all and not all(token in city_value for token in city_tokens_all):
        return False
    if org_tokens_all and not all(token in org_value for token in org_tokens_all):
        return False
    return True


def is_valid_lead_record(record: dict[str, Any]) -> bool:
    if not _norm(record.get("practitioner_name")) and not _norm(record.get("organization_name")):
        return False
    return True


def _find_by_sql(where_sql: str, params: dict[str, Any]) -> ProfessionalLead | None:
    row = db.session.execute(
        text(f"SELECT id FROM professional_leads WHERE {where_sql} ORDER BY id DESC LIMIT 1"),
        params,
    ).fetchone()
    if not row:
        return None
    return db.session.get(ProfessionalLead, int(row[0]))


def find_existing_professional_lead(
    record: dict[str, Any],
    *,
    columns: set[str],
) -> ProfessionalLead | None:
    source = "esante_fhir"
    source_role_id = _norm(record.get("source_external_id")) or None
    practitioner_identifier = _norm(record.get("practitioner_identifier")) or None
    practitioner_name = _norm(record.get("practitioner_name")) or None
    organization_name = _norm(record.get("organization_name")) or None
    postal_code = _norm(record.get("postal_code")) or None

    # A) source + source_external_id
    if source_role_id:
        if "source_external_id" in columns:
            if hasattr(ProfessionalLead, "source_external_id"):
                row = (
                    ProfessionalLead.query.filter(
                        func.lower(ProfessionalLead.source) == source,
                        getattr(ProfessionalLead, "source_external_id") == source_role_id,
                    )
                    .order_by(ProfessionalLead.id.desc())
                    .first()
                )
                if row:
                    return row
            else:
                row = _find_by_sql(
                    "lower(source)=:source AND source_external_id=:source_external_id",
                    {"source": source, "source_external_id": source_role_id},
                )
                if row:
                    return row
        elif "notes" in columns:
            marker = f"[esante_role_id={_norm_lower(source_role_id)}]"
            row = _find_by_sql(
                "lower(source)=:source AND lower(coalesce(notes,'')) LIKE :marker",
                {"source": source, "marker": f"%{marker}%"},
            )
            if row:
                return row

    # B) practitioner_identifier
    if practitioner_identifier:
        if "practitioner_identifier" in columns:
            row = _find_by_sql(
                "lower(coalesce(practitioner_identifier,''))=:pid",
                {"pid": _norm_lower(practitioner_identifier)},
            )
            if row:
                return row
        elif "notes" in columns:
            marker = f"[esante_practitioner_identifier={_norm_lower(practitioner_identifier)}]"
            row = _find_by_sql(
                "lower(coalesce(notes,'')) LIKE :marker",
                {"marker": f"%{marker}%"},
            )
            if row:
                return row

    # C) fallback tuple (practitioner_name, organization_name, postal_code)
    if practitioner_name and organization_name and postal_code:
        if "postal_code" in columns:
            row = _find_by_sql(
                "lower(coalesce(full_name,''))=:full_name "
                "AND lower(coalesce(organization,''))=:organization "
                "AND lower(coalesce(postal_code,''))=:postal_code",
                {
                    "full_name": _norm_lower(practitioner_name),
                    "organization": _norm_lower(organization_name),
                    "postal_code": _norm_lower(postal_code),
                },
            )
        elif "notes" in columns:
            marker = f"[esante_postal_code={_norm_lower(postal_code)}]"
            row = _find_by_sql(
                "lower(coalesce(full_name,''))=:full_name "
                "AND lower(coalesce(organization,''))=:organization "
                "AND lower(coalesce(notes,'')) LIKE :marker",
                {
                    "full_name": _norm_lower(practitioner_name),
                    "organization": _norm_lower(organization_name),
                    "marker": f"%{marker}%",
                },
            )
        else:
            row = (
                ProfessionalLead.query.filter(
                    func.lower(ProfessionalLead.full_name) == _norm_lower(practitioner_name),
                    func.lower(ProfessionalLead.organization) == _norm_lower(organization_name),
                )
                .order_by(ProfessionalLead.id.desc())
                .first()
            )
        if row:
            return row

    return None


def _build_trace_note(record: dict[str, Any], batch_label: str) -> str:
    return (
        f"[esante_role_id={_norm_lower(record.get('source_external_id'))}]"
        f"[esante_practitioner_identifier={_norm_lower(record.get('practitioner_identifier'))}]"
        f"[esante_organization_identifier={_norm_lower(record.get('organization_identifier'))}]"
        f"[esante_postal_code={_norm_lower(record.get('postal_code'))}]"
        f"[esante_batch={_norm(batch_label)}]"
    )


def apply_non_destructive_update(
    existing: ProfessionalLead,
    new_data: dict[str, Any],
    *,
    columns: set[str],
    batch_label: str,
) -> bool:
    changed = False
    sql_updates: dict[str, object] = {}

    def fill_if_empty(attr: str, value: str | None):
        nonlocal changed
        if not value or not hasattr(existing, attr):
            return
        current = _norm(getattr(existing, attr, None))
        if not current:
            setattr(existing, attr, value)
            changed = True

    fill_if_empty("full_name", _norm(new_data.get("full_name")) or None)
    fill_if_empty("organization", _norm(new_data.get("organization")) or None)
    fill_if_empty("city", _norm(new_data.get("city")) or None)
    fill_if_empty("profession", _norm(new_data.get("profession")) or None)
    fill_if_empty("phone", _norm(new_data.get("phone")) or None)

    incoming_email = _norm_lower(new_data.get("email")) or None
    if incoming_email and hasattr(existing, "email"):
        current_email = _norm_lower(getattr(existing, "email", None))
        if (not current_email) or _is_synthetic_email(current_email):
            if current_email != incoming_email:
                setattr(existing, "email", incoming_email)
                changed = True

    if hasattr(existing, "source") and not _norm(getattr(existing, "source", None)):
        setattr(existing, "source", "esante_fhir")
        changed = True
    if hasattr(existing, "status"):
        if _norm_lower(getattr(existing, "status", None)) in ("", "new"):
            setattr(existing, "status", "imported")
            changed = True

    if "notes" in columns:
        note = _build_trace_note(new_data, batch_label)
        if hasattr(existing, "notes"):
            merged = _append_note(getattr(existing, "notes", None), note)
            if merged != (getattr(existing, "notes", None) or ""):
                setattr(existing, "notes", merged)
                changed = True
        else:
            sql_updates["notes"] = _append_note(None, note)
            changed = True

    source_url = _norm(new_data.get("source_url")) or None
    if source_url and "source_url" in columns:
        if hasattr(existing, "source_url"):
            current = _norm(getattr(existing, "source_url", None))
            if not current:
                setattr(existing, "source_url", source_url)
                changed = True
        else:
            sql_updates.setdefault("source_url", source_url)
            changed = True

    source_external_id = _norm(new_data.get("source_external_id")) or None
    if source_external_id and "source_external_id" in columns and not hasattr(
        existing, "source_external_id"
    ):
        sql_updates.setdefault("source_external_id", source_external_id)
        changed = True

    if batch_label and "import_batch" in columns:
        if hasattr(existing, "import_batch"):
            current = _norm(getattr(existing, "import_batch", None))
            if not current:
                setattr(existing, "import_batch", batch_label)
                changed = True
        else:
            sql_updates.setdefault("import_batch", batch_label)
            changed = True

    metadata_obj = {
        "source_external_id": new_data.get("source_external_id"),
        "practitioner_identifier": new_data.get("practitioner_identifier"),
        "organization_identifier": new_data.get("organization_identifier"),
        "postal_code": new_data.get("postal_code"),
        "address_line1": new_data.get("address_line1"),
        "specialties": new_data.get("specialties") or [],
        "active": new_data.get("active"),
    }
    metadata_json = _json_compact(metadata_obj)
    for col in ("source_metadata", "source_meta_json", "raw_json", "meta_json"):
        if col in columns:
            if hasattr(existing, col):
                current = _norm(getattr(existing, col, None))
                if not current:
                    setattr(existing, col, metadata_json)
                    changed = True
            else:
                sql_updates.setdefault(col, metadata_json)
                changed = True
            break

    if changed and sql_updates:
        set_clause = ", ".join(f"{col} = :{col}" for col in sql_updates.keys())
        params = dict(sql_updates)
        params["id"] = int(existing.id)
        db.session.execute(
            text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
            params,
        )

    return changed


def create_new_professional_lead(
    data: dict[str, Any],
    *,
    columns: set[str],
    batch_label: str,
) -> ProfessionalLead:
    full_name = _norm(data.get("full_name")) or _norm(data.get("organization")) or None
    profession = _norm(data.get("profession")) or "Professionnel de sante"
    email = _norm_lower(data.get("email")) or _synthetic_email(
        data.get("source_external_id"), data.get("practitioner_name")
    )

    lead = ProfessionalLead(
        email=email,
        full_name=full_name,
        phone=_norm(data.get("phone")) or None,
        city=_norm(data.get("city")) or None,
        profession=profession,
        organization=_norm(data.get("organization")) or None,
        source="esante_fhir",
        status="imported",
        notes=_build_trace_note(data, batch_label),
        created_at=datetime.now(UTC),
    )
    db.session.add(lead)
    db.session.flush()

    sql_updates: dict[str, object] = {}
    source_url = _norm(data.get("source_url")) or None
    if source_url and "source_url" in columns:
        if hasattr(lead, "source_url"):
            setattr(lead, "source_url", source_url)
        else:
            sql_updates["source_url"] = source_url

    source_external_id = _norm(data.get("source_external_id")) or None
    if source_external_id and "source_external_id" in columns:
        if hasattr(lead, "source_external_id"):
            setattr(lead, "source_external_id", source_external_id)
        else:
            sql_updates["source_external_id"] = source_external_id

    if batch_label and "import_batch" in columns:
        if hasattr(lead, "import_batch"):
            setattr(lead, "import_batch", batch_label)
        else:
            sql_updates["import_batch"] = batch_label

    metadata_obj = {
        "source_external_id": data.get("source_external_id"),
        "practitioner_identifier": data.get("practitioner_identifier"),
        "organization_identifier": data.get("organization_identifier"),
        "postal_code": data.get("postal_code"),
        "address_line1": data.get("address_line1"),
        "specialties": data.get("specialties") or [],
        "active": data.get("active"),
        "raw": data.get("raw") or {},
    }
    metadata_json = _json_compact(metadata_obj)
    for col in ("source_metadata", "source_meta_json", "raw_json", "meta_json"):
        if col in columns:
            if hasattr(lead, col):
                setattr(lead, col, metadata_json)
            else:
                sql_updates[col] = metadata_json
            break

    if sql_updates:
        set_clause = ", ".join(f"{col} = :{col}" for col in sql_updates.keys())
        params = dict(sql_updates)
        params["id"] = int(lead.id)
        db.session.execute(
            text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
            params,
        )

    return lead


def print_import_summary(
    stats: dict[str, int], *, batch_label: str | None = None, city: str | None = None
) -> None:
    if batch_label:
        print(f"Batch: {batch_label}")
    if city:
        print(f"City: {city}")
    print(f"Fetched_remote: {stats['fetched_remote']}")
    print(f"Matched_local_filters: {stats['matched_local_filters']}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Updated: {stats['updated']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Duplicates: {stats['duplicates']}")
    print(f"Errors: {stats['errors']}")


def print_field_profile(records: list[dict[str, Any]]) -> None:
    fields = ("city", "postal_code", "organization_name")
    print("Field Profiling (post local filters)")
    for field in fields:
        freq = Counter()
        empty_count = 0
        for rec in records:
            value = _norm(rec.get(field))
            if not value:
                empty_count += 1
                continue
            freq[value] += 1
        print(f"- {field}:")
        print(f"  empty_or_null={empty_count}")
        for val, cnt in freq.most_common(30):
            print(f"  {cnt:4d}  {val}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import professionals from eSante FHIR API.")
    parser.add_argument("--city", default="", help="Local city filter, exact match (case-insensitive).")
    parser.add_argument("--postal-code", default="", help="Local postal code filter, exact match.")
    parser.add_argument(
        "--organization-name-contains",
        default="",
        help="Local organization name substring filter (case-insensitive).",
    )
    parser.add_argument(
        "--city-token-all",
        default="",
        help="Require all tokens to be present in normalized city.",
    )
    parser.add_argument(
        "--organization-token-all",
        default="",
        help="Require all tokens to be present in normalized organization name.",
    )
    parser.add_argument("--count", type=int, default=50, help="Page size")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum number of pages")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep between pages")
    parser.add_argument("--output", default="esante_import.json", help="Output JSON file")
    parser.add_argument(
        "--profile-fields",
        action="store_true",
        help="Print top frequencies for city/postal_code/organization_name after local filtering.",
    )
    parser.add_argument("--dry-run", action="store_true", help="No DB writes.")
    parser.add_argument("--db-write", action="store_true", help="Enable DB upsert mode.")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Enable non-destructive enrichment of existing leads.",
    )
    parser.add_argument(
        "--import-batch-label",
        default="",
        help="Optional batch label for traceability.",
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required with --db-write when not --dry-run.",
    )
    args = parser.parse_args()

    try:
        records = run_import(
            city=args.city,
            count=args.count,
            max_pages=args.max_pages,
            sleep_seconds=args.sleep,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    normalized_records = [normalize_fhir_record(raw) for raw in records]
    filtered_records = [
        rec
        for rec in normalized_records
        if matches_local_filters(
            rec,
            city=args.city,
            postal_code=args.postal_code,
            organization_name_contains=args.organization_name_contains,
            city_token_all=args.city_token_all,
            organization_token_all=args.organization_token_all,
        )
    ]

    stats = {
        "fetched_remote": len(records),
        "matched_local_filters": len(filtered_records),
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "duplicates": 0,
        "errors": 0,
    }

    batch_label = _norm(args.import_batch_label) or datetime.now(UTC).strftime(
        "esante_%Y%m%dT%H%M%SZ"
    )

    if args.dry_run:
        print("Dry-run mode enabled. No DB writes performed.")
        if args.profile_fields:
            print_field_profile(filtered_records)
        print(f"Saved to {args.output}")
        print_import_summary(stats, batch_label=batch_label, city=args.city)
        return 0

    if not args.db_write:
        print("DB write mode disabled. Records exported only.")
        if args.profile_fields:
            print_field_profile(filtered_records)
        print(f"Saved to {args.output}")
        print_import_summary(stats, batch_label=batch_label, city=args.city)
        return 0

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 2
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2

        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        if "professional_leads" not in table_names:
            print("ERROR: professional_leads table is missing.")
            return 3
        columns = {
            c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")
        }

        for normalized in filtered_records:
            try:
                if not is_valid_lead_record(normalized):
                    stats["skipped"] += 1
                    continue

                existing = find_existing_professional_lead(normalized, columns=columns)
                if existing:
                    if not args.update_existing:
                        stats["duplicates"] += 1
                        stats["skipped"] += 1
                        continue
                    changed = apply_non_destructive_update(
                        existing,
                        normalized,
                        columns=columns,
                        batch_label=batch_label,
                    )
                    if changed:
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                    continue

                create_new_professional_lead(
                    normalized,
                    columns=columns,
                    batch_label=batch_label,
                )
                stats["inserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
                db.session.rollback()
                print(f"ERROR record failed: {exc}")

        db.session.commit()

    if args.profile_fields:
        print_field_profile(filtered_records)
    print(f"Saved to {args.output}")
    print_import_summary(stats, batch_label=batch_label, city=args.city)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
