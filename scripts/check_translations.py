#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import polib


T_CALL_RE = re.compile(
    r"""\bt\s*\(\s*(["'])(?P<key>[^"']+)\1""",
    re.VERBOSE,
)
DATA_I18N_RE = re.compile(r"""data-i18n\s*=\s*(["'])(?P<key>[^"']+)\1""")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="CI translation checks for ui_keys + locales.")
    ap.add_argument("--registry", default="i18n/ui_keys.json")
    ap.add_argument("--templates-dir", default="templates")
    ap.add_argument("--translations-dir", default="translations")
    ap.add_argument("--domain", default="messages")
    ap.add_argument("--fail-locales", default="fr", help="Comma list; missing keys here fail CI.")
    ap.add_argument("--warn-locales", default="en,de,bg", help="Comma list; missing keys here warn only.")
    ap.add_argument("--show", type=int, default=50, help="Max keys to print per section.")
    return ap.parse_args()


def load_registry(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        key = str(r.get("key") or "").strip()
        if not key:
            continue
        out.append(
            {
                "key": key,
                "default": str(r.get("default") or "").strip(),
                "domain": str(r.get("domain") or "").strip(),
                "kind": str(r.get("kind") or "tkey").strip() or "tkey",
            }
        )
    return out


def extract_t_keys(templates_dir: Path) -> set[str]:
    found: set[str] = set()
    for ext in (".html", ".jinja", ".jinja2"):
        for fp in templates_dir.rglob(f"*{ext}"):
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in T_CALL_RE.finditer(text):
                k = (m.group("key") or "").strip()
                if k:
                    found.add(k)
            for m in DATA_I18N_RE.finditer(text):
                k = (m.group("key") or "").strip()
                if k:
                    found.add(k)
    return found


def load_po_catalog(po_path: Path) -> tuple[set[str], set[str]]:
    if not po_path.exists():
        return set(), set()
    po = polib.pofile(str(po_path))
    msgids: set[str] = set()
    translated: set[str] = set()
    for e in po:
        if e.obsolete or not e.msgid:
            continue
        msgid = str(e.msgid)
        msgids.add(msgid)
        msgstr = str(e.msgstr or "").strip()
        if msgstr and msgstr != msgid:
            translated.add(msgid)
    return msgids, translated


def source_msgid(key: str) -> str:
    if key.startswith("msgid:"):
        return key.split("msgid:", 1)[1].strip()
    return key


def exists_for_locale(entry: dict, locale: str, catalogs: dict[str, tuple[set[str], set[str]]]) -> bool:
    key = entry["key"]
    default = entry.get("default") or ""
    msgid = source_msgid(key)
    msgids, translated = catalogs.get(locale, (set(), set()))

    if locale == "fr":
        if key.startswith("msgid:"):
            return bool(msgid)
        if default:
            return True
        return msgid in msgids

    # Non-FR locales: require real translated msgstr in PO.
    return msgid in translated


def main() -> int:
    args = parse_args()
    registry = load_registry(Path(args.registry))
    registry_keys = {r["key"] for r in registry}

    # 1) Registry sync: t() keys from templates must exist in ui_keys.json
    template_t_keys = extract_t_keys(Path(args.templates_dir))
    missing_registry = sorted(k for k in template_t_keys if k not in registry_keys)

    fail_locales = [x.strip().lower() for x in args.fail_locales.split(",") if x.strip()]
    warn_locales = [x.strip().lower() for x in args.warn_locales.split(",") if x.strip()]
    all_locales = sorted(set(fail_locales + warn_locales))

    catalogs: dict[str, tuple[set[str], set[str]]] = {}
    for locale in all_locales:
        po = Path(args.translations_dir) / locale / "LC_MESSAGES" / f"{args.domain}.po"
        catalogs[locale] = load_po_catalog(po)

    missing_by_locale: dict[str, list[str]] = {}
    for locale in all_locales:
        missing = [r["key"] for r in registry if not exists_for_locale(r, locale, catalogs)]
        missing_by_locale[locale] = missing

    # Output
    if missing_registry:
        print("ERROR: registry sync failed (keys used in templates but missing in ui_keys.json):")
        for k in missing_registry[: args.show]:
            print(f"  - {k}")
        if len(missing_registry) > args.show:
            print(f"  ... +{len(missing_registry) - args.show} more")

    for locale in fail_locales:
        missing = missing_by_locale.get(locale, [])
        if missing:
            print(f"ERROR: missing {locale.upper()} translations: {len(missing)}")
            for k in missing[: args.show]:
                print(f"  - {k}")
            if len(missing) > args.show:
                print(f"  ... +{len(missing) - args.show} more")
        else:
            print(f"OK: {locale.upper()} has full coverage for registry keys.")

    for locale in warn_locales:
        missing = missing_by_locale.get(locale, [])
        if missing:
            print(f"WARN: missing {locale.upper()} translations: {len(missing)}")
        else:
            print(f"OK: {locale.upper()} has full coverage for registry keys.")

    fail = bool(missing_registry)
    for locale in fail_locales:
        if missing_by_locale.get(locale):
            fail = True

    if fail:
        print("FAIL: i18n check failed.")
        return 1
    print("PASS: i18n check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
