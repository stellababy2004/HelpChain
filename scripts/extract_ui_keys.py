#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract UI translation keys from Jinja templates and update i18n/ui_keys.json.

Targets:
- {{ t("key") }}
- {{ t('key', 'Default') }}
- optional data-i18n="key"

Usage:
  python scripts/extract_ui_keys.py --templates-dir templates --registry i18n/ui_keys.json --write
  python scripts/extract_ui_keys.py --write --report reports/ui_keys_extract.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

T_CALL_RE = re.compile(
    r"""\bt\s*\(\s*
        (?P<q1>["'])(?P<key>[^"']+)(?P=q1)
        \s*
        (?:,\s*(?P<q2>["'])(?P<default>[^"']*)(?P=q2))?
        \s*\)
    """,
    re.VERBOSE,
)
DATA_I18N_RE = re.compile(r"""data-i18n\s*=\s*(?P<q>["'])(?P<key>[^"']+)(?P=q)""")
# Matches _("Text") or _('Text') - basic string literal only
GETTEXT_CALL_RE = re.compile(
    r"""\b_\s*\(\s*(?P<q>["'])(?P<msgid>[^"']+)(?P=q)\s*\)""",
    re.VERBOSE,
)
# Matches simple {% trans %} ... {% endtrans %} blocks
TRANS_BLOCK_RE = re.compile(
    r"""{%\s*trans\s*%}(?P<body>.*?){%\s*endtrans\s*%}""",
    re.DOTALL,
)


@dataclass(frozen=True)
class FoundKey:
    key: str
    default: str | None
    domain: str
    kind: str = "tkey"
    tier: str = "core"


def _looks_like_core_msgid(msgid: str, domain: str) -> bool:
    s = (msgid or "").strip()
    if not s:
        return False
    if "\n" in s or "\r" in s:
        return False
    if len(s) > 50:
        return False

    lowered = s.lower()
    bad_tokens = ["http://", "https://", "www.", "@", ".com", ".fr", ".bg", ".net"]
    if any(token in lowered for token in bad_tokens):
        return False
    if s.count(".") > 1:
        return False
    if s.count(",") > 2:
        return False
    if ":" in s and len(s.split(":", 1)[1].strip()) > 20:
        return False

    paragraph_words = [
        "veuillez",
        "merci",
        "votre",
        "vos",
        "nous",
        "afin",
        "pour",
        "conçu",
        "opéré",
        "please",
        "thank",
        "your",
        "we",
        "designed",
        "operated",
    ]
    if any(w in lowered for w in paragraph_words) and len(s) > 28:
        return False
    return True


def infer_domain_from_path(path: Path) -> str:
    p = str(path).replace("\\", "/").lower()
    if "/templates/admin/" in p or p.startswith("templates/admin/"):
        if "translations" in p:
            return "admin_translations"
        if "request_details" in p or "case" in p:
            return "admin_case"
        if "/requests" in p or "admin-requests" in p or "ops" in p:
            return "admin_requests"
        return "admin_nav"

    if "/templates/volunteer/" in p or p.startswith("templates/volunteer/") or "volunteer" in p:
        return "volunteer_nav"

    if "base" in p or "navbar" in p or "/partials/" in p or "nav" in p:
        return "public_nav"

    return "public"


def iter_template_files(templates_dir: Path) -> Iterable[Path]:
    for ext in (".html", ".jinja", ".jinja2"):
        yield from templates_dir.rglob(f"*{ext}")


def extract_from_text(text: str, domain: str, include_data_i18n: bool) -> list[FoundKey]:
    found: list[FoundKey] = []
    for match in T_CALL_RE.finditer(text):
        key = (match.group("key") or "").strip()
        default = match.group("default")
        default = default.strip() if default is not None else None
        if key:
            found.append(
                FoundKey(
                    key=key,
                    default=default,
                    domain=domain,
                    kind="tkey",
                    tier="core",
                )
            )

    if include_data_i18n:
        for match in DATA_I18N_RE.finditer(text):
            key = (match.group("key") or "").strip()
            if key:
                found.append(
                    FoundKey(
                        key=key,
                        default=None,
                        domain=domain,
                        kind="tkey",
                        tier="core",
                    )
                )

    for match in GETTEXT_CALL_RE.finditer(text):
        msgid = (match.group("msgid") or "").strip()
        if msgid:
            tier = "core" if _looks_like_core_msgid(msgid, domain) else "inventory"
            found.append(
                FoundKey(
                    key=f"msgid:{msgid}",
                    default=msgid,
                    domain=domain,
                    kind="msgid",
                    tier=tier,
                )
            )

    for match in TRANS_BLOCK_RE.finditer(text):
        body = (match.group("body") or "").strip()
        if not body:
            continue
        if "{{" in body or "{%" in body:
            continue
        msgid = " ".join(body.split())
        if msgid:
            tier = "core" if _looks_like_core_msgid(msgid, domain) else "inventory"
            found.append(
                FoundKey(
                    key=f"msgid:{msgid}",
                    default=msgid,
                    domain=domain,
                    kind="msgid",
                    tier=tier,
                )
            )

    return found


def load_registry(registry_path: Path) -> list[dict]:
    if not registry_path.exists():
        return []
    return json.loads(registry_path.read_text(encoding="utf-8"))


def save_registry(registry_path: Path, entries: list[dict]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates-dir", default="templates")
    ap.add_argument("--registry", default="i18n/ui_keys.json")
    ap.add_argument("--write", action="store_true", help="Write changes to registry")
    ap.add_argument("--report", default="", help="Write JSON report")
    ap.add_argument(
        "--include-data-i18n",
        action="store_true",
        help="Also extract data-i18n attributes",
    )
    args = ap.parse_args()

    templates_dir = Path(args.templates_dir)
    registry_path = Path(args.registry)

    existing = load_registry(registry_path)
    by_key: dict[str, dict] = {e.get("key"): e for e in existing if e.get("key")}

    found_keys: dict[str, FoundKey] = {}
    occurrences: dict[str, int] = {}

    for fp in iter_template_files(templates_dir):
        try:
            text = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        domain = infer_domain_from_path(fp)
        extracted = extract_from_text(
            text, domain=domain, include_data_i18n=args.include_data_i18n
        )
        for fk in extracted:
            occurrences[fk.key] = occurrences.get(fk.key, 0) + 1
            if fk.key not in found_keys:
                found_keys[fk.key] = fk
            else:
                prev = found_keys[fk.key]
                dom = prev.domain
                if prev.domain != "admin" and fk.domain == "admin":
                    dom = "admin"
                dflt = prev.default or fk.default
                kind = prev.kind or fk.kind
                tier = "core" if ("core" in {prev.tier, fk.tier}) else "inventory"
                found_keys[fk.key] = FoundKey(
                    key=fk.key, default=dflt, domain=dom, kind=kind, tier=tier
                )

    new_entries: list[dict] = []
    updated_existing = 0

    for key, fk in sorted(found_keys.items(), key=lambda kv: kv[0]):
        if key in by_key:
            row = by_key[key]
            changed = False
            if row.get("domain") != fk.domain:
                row["domain"] = fk.domain
                changed = True
            if (not row.get("default")) and fk.default:
                row["default"] = fk.default
                changed = True
            if not row.get("kind"):
                row["kind"] = fk.kind
                changed = True
            if row.get("kind") == "msgid":
                dom = str(row.get("domain") or fk.domain or "public")
                dflt = str(row.get("default") or fk.default or "")
                row["tier"] = (
                    "core" if _looks_like_core_msgid(dflt, dom) else "inventory"
                )
                changed = True
            elif not row.get("tier"):
                row["tier"] = "core"
                changed = True
            if changed:
                updated_existing += 1
        else:
            entry = {
                "key": fk.key,
                "domain": fk.domain,
                "default": fk.default or "",
                "kind": fk.kind,
                "tier": fk.tier,
            }
            by_key[key] = entry
            new_entries.append(entry)

    unused = []
    for row in existing:
        key = row.get("key")
        if key and key not in found_keys:
            unused.append(key)

    final_entries: list[dict] = []
    seen = set()
    for row in existing:
        key = row.get("key")
        if not key or key in seen:
            continue
        final_entries.append(by_key[key])
        seen.add(key)
    for row in new_entries:
        key = row["key"]
        if key in seen:
            continue
        final_entries.append(row)
        seen.add(key)

    report = {
        "templates_dir": str(templates_dir),
        "registry": str(registry_path),
        "found_total_unique": len(found_keys),
        "found_total_occurrences": sum(occurrences.values()),
        "new_keys": [e["key"] for e in new_entries],
        "updated_existing": updated_existing,
        "unused_registry_keys": unused,
        "top_occurrences": sorted(
            [{"key": k, "count": c} for k, c in occurrences.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:20],
    }

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if args.write:
        save_registry(registry_path, final_entries)

    print(
        f"[ui_keys] found unique: {report['found_total_unique']}, "
        f"occurrences: {report['found_total_occurrences']}"
    )
    print(
        f"[ui_keys] new keys: {len(report['new_keys'])}, "
        f"updated existing: {report['updated_existing']}"
    )
    print(f"[ui_keys] unused in registry: {len(report['unused_registry_keys'])}")
    if report["new_keys"]:
        preview = ", ".join(report["new_keys"][:30])
        if len(report["new_keys"]) > 30:
            preview += " ..."
        print(f"[ui_keys] added: {preview}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
