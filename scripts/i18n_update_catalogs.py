#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from babel.messages import mofile, pofile


def parse_args():
    p = argparse.ArgumentParser(description="Update gettext catalogs from a POT template without pybabel rename/remove.")
    p.add_argument("--pot", default="messages.pot", help="Path to messages.pot")
    p.add_argument("--translations-dir", default="translations", help="Translations root")
    p.add_argument("--domain", default="messages", help="Domain filename without extension")
    p.add_argument("--langs", nargs="*", default=[], help="Optional language codes")
    return p.parse_args()


def load_po(path: Path, locale: str):
    with path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def save_po(path: Path, catalog):
    with path.open("wb") as f:
        pofile.write_po(f, catalog, width=120)


def load_mo(path: Path):
    with path.open("rb") as f:
        return mofile.read_mo(f)


def msg_key(msg):
    return (getattr(msg, "context", None), msg.id)


def main():
    args = parse_args()
    pot_path = Path(args.pot)
    root = Path(args.translations_dir)
    if not pot_path.exists():
        raise SystemExit(f"POT not found: {pot_path}")
    if not root.exists():
        raise SystemExit(f"Translations dir not found: {root}")

    with pot_path.open("r", encoding="utf-8") as f:
        template = pofile.read_po(f)

    po_paths = sorted(root.glob(f"*/LC_MESSAGES/{args.domain}.po"))
    if args.langs:
        wanted = {x.strip().lower() for x in args.langs if x.strip()}
        po_paths = [p for p in po_paths if p.parts[-3].lower() in wanted]

    updated = 0
    failed = 0
    for po_path in po_paths:
        lang = po_path.parts[-3]
        try:
            current = load_po(po_path, locale=lang)
            mo_path = po_path.with_suffix(".mo")
            source_catalog = load_mo(mo_path) if mo_path.exists() else current

            with pot_path.open("r", encoding="utf-8") as f:
                merged = pofile.read_po(f, locale=lang)

            source_map = {msg_key(m): m for m in source_catalog if getattr(m, "id", None)}
            for msg in merged:
                if not getattr(msg, "id", None):
                    continue
                prev = source_map.get(msg_key(msg))
                if prev is None:
                    continue
                if prev.string is not None:
                    msg.string = prev.string
                if getattr(prev, "flags", None):
                    msg.flags.update(prev.flags)

            # Preserve existing metadata headers if available.
            try:
                if getattr(current, "revision_date", None):
                    merged.revision_date = current.revision_date
                if getattr(current, "last_translator", None):
                    merged.last_translator = current.last_translator
                if getattr(current, "language_team", None):
                    merged.language_team = current.language_team
                if getattr(current, "project", None):
                    merged.project = current.project
                if getattr(current, "version", None):
                    merged.version = current.version
                if getattr(current, "msgid_bugs_address", None):
                    merged.msgid_bugs_address = current.msgid_bugs_address
            except Exception:
                pass

            save_po(po_path, merged)
            updated += 1
            print(f"[OK] {lang}: {po_path}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {lang}: {po_path} -> {e}")

    print(f"Done. updated={updated} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
