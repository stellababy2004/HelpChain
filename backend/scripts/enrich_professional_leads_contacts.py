from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from sqlalchemy import inspect, or_, text

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

FHIR_BASE_URL = os.getenv("ESANTE_FHIR_BASE_URL", "https://gateway.api.esante.gouv.fr/fhir")
HTTP_TIMEOUT = 20

EMAIL_RE = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:(?:\+33|0)\s*[1-9](?:[\s.\-]?\d{2}){4})")

def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def is_synthetic_email(email: str | None) -> bool:
    value = _norm_lower(email)
    return value.startswith("no-email+") and value.endswith("@esante-fhir.local")


def normalize_search_query(value: str | None) -> str:
    txt = _norm_lower(value).replace("-", " ")
    return " ".join(txt.split())


def _json_compact(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _extract_role_id(lead: ProfessionalLead) -> str | None:
    source_url = _norm(getattr(lead, "source_url", None))
    if source_url:
        match = re.search(r"/PractitionerRole/([^/?#]+)", source_url)
        if match:
            return match.group(1)

    notes = _norm(getattr(lead, "notes", None))
    if notes:
        match = re.search(r"(?:role_id|source_role_id)\s*[:=]\s*([A-Za-z0-9\-_.]+)", notes)
        if match:
            return match.group(1)
    return None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "ESANTE-API-KEY": api_key,
        "Accept": "application/fhir+json",
        "User-Agent": "HelpChain-ContactEnrichment/1.0",
    }


def _extract_telecom(resource: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {"email": None, "phone": None, "url": None}
    for telecom in resource.get("telecom", []) or []:
        system = _norm_lower(telecom.get("system"))
        value = _norm(telecom.get("value"))
        if not value:
            continue
        if system == "email" and not out["email"]:
            out["email"] = value
        elif system == "phone" and not out["phone"]:
            out["phone"] = value
        elif system in {"url", "website"} and not out["url"]:
            out["url"] = value
    return out


def _get_resource(session: requests.Session, api_key: str, path: str) -> dict[str, Any] | None:
    resp = session.get(
        f"{FHIR_BASE_URL}/{path.lstrip('/')}",
        headers=_headers(api_key),
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        return None
    return resp.json()


def _organization_name_from_role(role: dict[str, Any]) -> str | None:
    org = role.get("organization") or {}
    display = _norm(org.get("display"))
    return display or None


def _organization_ref_from_role(role: dict[str, Any]) -> str | None:
    ref = _norm((role.get("organization") or {}).get("reference"))
    if "/" in ref:
        return ref.split("/")[-1]
    return ref or None


def enrich_from_identifiers(
    lead: ProfessionalLead,
    session: requests.Session,
    api_key: str | None,
) -> dict[str, Any]:
    if not api_key:
        return {}

    role_id = _extract_role_id(lead)
    if not role_id:
        return {}

    role = _get_resource(session, api_key, f"PractitionerRole/{role_id}")
    if not role:
        return {}

    role_contact = _extract_telecom(role)
    org_ref = _organization_ref_from_role(role)
    org_name = _organization_name_from_role(role)
    org_contact: dict[str, str | None] = {"email": None, "phone": None, "url": None}
    if org_ref:
        org = _get_resource(session, api_key, f"Organization/{org_ref}")
        if org:
            org_contact = _extract_telecom(org)
            org_name = _norm(org.get("name")) or org_name

    email = role_contact.get("email") or org_contact.get("email")
    phone = role_contact.get("phone") or org_contact.get("phone")
    website = org_contact.get("url")
    if website and not website.startswith(("http://", "https://")):
        website = f"https://{website.lstrip('/')}"

    if not any([email, phone, website]):
        return {}

    return {
        "contact_email": email,
        "contact_phone": phone,
        "website_url": website,
        "contact_page_url": None,
        "contact_source": f"esante_fhir_identifier:{role_id}",
        "contact_confidence": "high",
        "organization_name": org_name,
    }


def enrich_from_public_web(
    lead: ProfessionalLead,
    session: requests.Session,
    api_key: str | None,
) -> dict[str, Any]:
    if not api_key:
        return {}

    organization = _norm(lead.organization)
    city = _norm(lead.city)
    if not organization:
        return {}

    params = [("name", organization), ("_count", "5")]
    if city:
        params.append(("address-city", city))

    resp = session.get(
        f"{FHIR_BASE_URL}/Organization",
        headers=_headers(api_key),
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        return {}

    bundle = resp.json()
    entries = bundle.get("entry", []) or []
    if not entries:
        return {}

    best = entries[0].get("resource", {}) or {}
    telecom = _extract_telecom(best)
    website = telecom.get("url")
    if website and not website.startswith(("http://", "https://")):
        website = f"https://{website.lstrip('/')}"

    if not any([telecom.get("email"), telecom.get("phone"), website]):
        return {}

    return {
        "contact_email": telecom.get("email"),
        "contact_phone": telecom.get("phone"),
        "website_url": website,
        "contact_page_url": None,
        "contact_source": "esante_fhir_org_search",
        "contact_confidence": "medium",
    }


def _same_domain(url_a: str, url_b: str) -> bool:
    try:
        host_a = urlparse(url_a).netloc.lower().replace("www.", "")
        host_b = urlparse(url_b).netloc.lower().replace("www.", "")
        return bool(host_a and host_b and host_a == host_b)
    except Exception:
        return False


def _extract_contact_from_text(text_body: str) -> dict[str, str | None]:
    emails = [m.group(1) for m in EMAIL_RE.finditer(text_body)]
    phones = [m.group(0) for m in PHONE_RE.finditer(text_body)]

    email = None
    for item in emails:
        if not is_synthetic_email(item):
            email = item
            break

    phone = phones[0] if phones else None
    return {"email": email, "phone": phone}


def extract_contact_from_website(session: requests.Session, website_url: str | None) -> dict[str, Any]:
    website = _norm(website_url)
    if not website:
        return {}

    candidate_urls = [website]
    for suffix in ("/contact", "/contactez-nous", "/nous-contacter"):
        candidate = website.rstrip("/") + suffix
        if candidate not in candidate_urls:
            candidate_urls.append(candidate)

    best_email = None
    best_phone = None
    contact_page_url = None
    scanned = 0

    for url in candidate_urls:
        if scanned >= 3:
            break
        scanned += 1
        try:
            resp = session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                continue
            final_url = resp.url
            if not _same_domain(website, final_url):
                continue
            found = _extract_contact_from_text(resp.text or "")
            if found.get("email") and not best_email:
                best_email = found["email"]
                contact_page_url = final_url
            if found.get("phone") and not best_phone:
                best_phone = found["phone"]
                contact_page_url = final_url
            if best_email and best_phone:
                break
        except Exception:
            continue

    if not any([best_email, best_phone]):
        return {}

    return {
        "contact_email": best_email,
        "contact_phone": best_phone,
        "website_url": website,
        "contact_page_url": contact_page_url,
        "contact_source": "organization_website",
        "contact_confidence": "high",
    }


def _load_json_field(existing: str | None) -> dict[str, Any]:
    raw = _norm(existing)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}
    return {}


def apply_contact_enrichment(
    lead: ProfessionalLead,
    enrichment: dict[str, Any],
    columns: set[str],
    db_write: bool,
) -> tuple[bool, bool, bool]:
    now_iso = datetime.now(UTC).isoformat()
    contact_email = _norm(enrichment.get("contact_email"))
    contact_phone = _norm(enrichment.get("contact_phone"))
    website_url = _norm(enrichment.get("website_url"))
    contact_page_url = _norm(enrichment.get("contact_page_url"))
    contact_source = _norm(enrichment.get("contact_source")) or "enrichment_v1"
    contact_confidence = _norm(enrichment.get("contact_confidence")) or "low"

    changed_email = False
    changed_phone = False
    changed_website = False

    # Non-destructive updates: only fill missing contact fields or replace synthetic email.
    current_email = _norm(getattr(lead, "email", None))
    if contact_email and (not current_email or is_synthetic_email(current_email)):
        if db_write:
            lead.email = contact_email
        changed_email = True

    current_phone = _norm(getattr(lead, "phone", None))
    if contact_phone and not current_phone:
        if db_write:
            lead.phone = contact_phone
        changed_phone = True

    sql_updates: dict[str, Any] = {}

    if website_url and "website_url" in columns:
        current_website = _norm(getattr(lead, "website_url", None))
        if not current_website:
            changed_website = True
            if db_write and hasattr(lead, "website_url"):
                setattr(lead, "website_url", website_url)
            elif db_write:
                sql_updates["website_url"] = website_url

    for key in ("contact_email", "contact_phone", "contact_page_url", "contact_source", "contact_confidence", "contact_last_checked_at"):
        if key not in columns:
            continue
        value = None
        if key == "contact_email":
            value = contact_email or None
        elif key == "contact_phone":
            value = contact_phone or None
        elif key == "contact_page_url":
            value = contact_page_url or None
        elif key == "contact_source":
            value = contact_source
        elif key == "contact_confidence":
            value = contact_confidence
        elif key == "contact_last_checked_at":
            value = now_iso
        if value is None:
            continue
        if db_write and hasattr(lead, key):
            current_val = _norm(getattr(lead, key, None))
            if key in {"contact_source", "contact_confidence", "contact_last_checked_at"} or not current_val:
                setattr(lead, key, value)
        elif db_write:
            sql_updates[key] = value

    metadata_payload = {
        "contact_email": contact_email or None,
        "contact_phone": contact_phone or None,
        "website_url": website_url or None,
        "contact_page_url": contact_page_url or None,
        "contact_source": contact_source,
        "contact_confidence": contact_confidence,
        "contact_last_checked_at": now_iso,
    }
    metadata_payload = {k: v for k, v in metadata_payload.items() if v}

    metadata_columns = ("source_metadata", "source_meta_json", "raw_json", "meta_json")
    wrote_metadata = False
    for col in metadata_columns:
        if col not in columns or not metadata_payload:
            continue
        existing = _load_json_field(getattr(lead, col, None) if hasattr(lead, col) else None)
        existing["contact_enrichment"] = metadata_payload
        metadata_json = _json_compact(existing)
        if db_write and hasattr(lead, col):
            setattr(lead, col, metadata_json)
        elif db_write:
            sql_updates[col] = metadata_json
        wrote_metadata = True
        break

    if db_write and not wrote_metadata and metadata_payload and "notes" in columns:
        note = (
            f"[contact_enrichment] email={contact_email or '-'} phone={contact_phone or '-'} "
            f"website={website_url or '-'} source={contact_source} confidence={contact_confidence} "
            f"checked={now_iso}"
        )
        current_notes = _norm(getattr(lead, "notes", None))
        merged = note if not current_notes else (current_notes if note in current_notes else f"{current_notes} | {note}")
        if hasattr(lead, "notes"):
            setattr(lead, "notes", merged)
        else:
            sql_updates["notes"] = merged

    if db_write and sql_updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in sql_updates.keys())
        params = dict(sql_updates)
        params["id"] = int(lead.id)
        db.session.execute(
            text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
            params,
        )

    return changed_email, changed_phone, changed_website


def print_summary(stats: dict[str, int]) -> None:
    print(f"scanned: {stats['scanned']}")
    print(f"enriched_email: {stats['enriched_email']}")
    print(f"enriched_phone: {stats['enriched_phone']}")
    print(f"enriched_website: {stats['enriched_website']}")
    print(f"skipped: {stats['skipped']}")
    print(f"errors: {stats['errors']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich esante_fhir professional leads with public contact data (safe v1)."
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db-write", action="store_true")
    parser.add_argument("--only-missing-contact", action="store_true")
    args = parser.parse_args()

    if args.db_write and args.dry_run:
        print("ERROR: use either --dry-run or --db-write, not both.")
        return 2

    db_write = bool(args.db_write)
    if not args.db_write:
        args.dry_run = True

    load_dotenv()
    api_key = _norm(os.getenv("ESANTE_API_KEY")) or None
    session = requests.Session()

    stats = {
        "scanned": 0,
        "enriched_email": 0,
        "enriched_phone": 0,
        "enriched_website": 0,
        "skipped": 0,
        "errors": 0,
    }

    with app.app_context():
        inspector = inspect(db.engine)
        columns = {
            c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")
        }

        query = ProfessionalLead.query.filter(ProfessionalLead.source == "esante_fhir").filter(
            or_(
                ProfessionalLead.email.is_(None),
                ProfessionalLead.email == "",
                ProfessionalLead.email.ilike("%@esante-fhir.local"),
            )
        )
        if args.only_missing_contact:
            query = query.filter(or_(ProfessionalLead.phone.is_(None), ProfessionalLead.phone == ""))

        leads = (
            query.order_by(ProfessionalLead.id.asc())
            .limit(max(1, int(args.limit)))
            .all()
        )

        for lead in leads:
            stats["scanned"] += 1
            try:
                enrichment = {}

                step_a = enrich_from_identifiers(lead, session, api_key)
                if step_a:
                    enrichment.update({k: v for k, v in step_a.items() if v})

                if not any(enrichment.get(k) for k in ("contact_email", "contact_phone", "website_url")):
                    step_b = enrich_from_public_web(lead, session, api_key)
                    if step_b:
                        enrichment.update({k: v for k, v in step_b.items() if v})

                if enrichment.get("website_url"):
                    step_c = extract_contact_from_website(session, enrichment.get("website_url"))
                    if step_c:
                        # Keep best confidence/source from website only when website extraction finds something.
                        enrichment.update({k: v for k, v in step_c.items() if v})

                if not any(enrichment.get(k) for k in ("contact_email", "contact_phone", "website_url")):
                    stats["skipped"] += 1
                    continue

                changed_email, changed_phone, changed_website = apply_contact_enrichment(
                    lead=lead,
                    enrichment=enrichment,
                    columns=columns,
                    db_write=db_write,
                )
                if changed_email:
                    stats["enriched_email"] += 1
                if changed_phone:
                    stats["enriched_phone"] += 1
                if changed_website:
                    stats["enriched_website"] += 1
                if not any([changed_email, changed_phone, changed_website]):
                    stats["skipped"] += 1

            except Exception:
                stats["errors"] += 1
                if db_write:
                    db.session.rollback()
                continue

        if db_write:
            db.session.commit()
            print("mode: db-write")
        else:
            db.session.rollback()
            print("mode: dry-run")

        print_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
