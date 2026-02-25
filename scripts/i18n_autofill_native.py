#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from babel.messages import pofile


CYRILLIC_RE = __import__("re").compile(r"[\u0400-\u04FF]")


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Autofill empty msgstr from msgid for likely native-language source strings (e.g. Cyrillic for bg).")
    p.add_argument("--langs", nargs="+", required=True, help="Locales to process (e.g. bg)")
    p.add_argument("--translations-dir", default="translations", help="Translations root")
    p.add_argument("--domain", default="messages", help="gettext domain (without .po)")
    p.add_argument("--dry-run", action="store_true", help="Report only, do not write")
    p.add_argument("--verbose", action="store_true", help="Print changed entries")
    return p.parse_args()


def load_catalog(path: Path, locale: str):
    with path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def save_catalog(path: Path, catalog) -> None:
    with path.open("wb") as f:
        pofile.write_po(f, catalog, width=120)


def is_empty_translation(msg) -> bool:
    s = msg.string
    if isinstance(s, str):
        return not s.strip()
    if isinstance(s, (tuple, list)):
        return not any((x or "").strip() for x in s)
    if isinstance(s, dict):
        return not any((x or "").strip() for x in s.values())
    return True


def likely_bg_native_source(msgid) -> bool:
    if isinstance(msgid, (tuple, list)):
        samples = [str(x) for x in msgid if x]
    else:
        samples = [str(msgid)]
    if not samples:
        return False
    text = " ".join(samples)
    return bool(CYRILLIC_RE.search(text))


def autofill_catalog(catalog, locale: str, verbose: bool = False) -> tuple[int, int]:
    scanned = 0
    changed = 0
    for msg in catalog:
        if not getattr(msg, "id", None) or getattr(msg, "obsolete", False):
            continue
        scanned += 1
        if locale != "bg":
            continue
        if not is_empty_translation(msg):
            continue
        if not likely_bg_native_source(msg.id):
            continue

        if isinstance(msg.id, str):
            msg.string = msg.id
        elif isinstance(msg.id, (tuple, list)):
            singular = str(msg.id[0]) if len(msg.id) > 0 else ""
            plural = str(msg.id[1]) if len(msg.id) > 1 else singular
            if isinstance(msg.string, dict):
                keys = sorted(msg.string.keys()) or [0, 1]
                msg.string = {k: (singular if int(k) == 0 else plural) for k in keys}
            elif isinstance(msg.string, list):
                n = max(len(msg.string), 2)
                msg.string = [singular if i == 0 else plural for i in range(n)]
            else:
                msg.string = (singular, plural)
        else:
            continue
        changed += 1
        if verbose:
            preview = str(msg.id[0] if isinstance(msg.id, (tuple, list)) else msg.id).replace("\n", "\\n")
            if len(preview) > 100:
                preview = preview[:97] + "..."
            print(f"  [FILL] {preview}")
    return scanned, changed


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()
    root = Path(args.translations_dir)
    total_changed = 0
    for lang in args.langs:
        po_path = root / lang / "LC_MESSAGES" / f"{args.domain}.po"
        if not po_path.exists():
            print(f"[SKIP {lang}] missing PO: {po_path}")
            continue
        catalog = load_catalog(po_path, lang)
        scanned, changed = autofill_catalog(catalog, lang, verbose=args.verbose)
        print(f"[{lang}] scanned={scanned} autofilled={changed}")
        total_changed += changed
        if changed and not args.dry_run:
            save_catalog(po_path, catalog)
    print(f"Done. total_autofilled={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

