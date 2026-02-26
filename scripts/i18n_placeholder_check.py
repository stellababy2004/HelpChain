#!/usr/bin/env python3
"""
Check placeholder mismatches in gettext PO files.

Detects mismatches between source msgid placeholders and translated msgstr placeholders:
- Jinja placeholders: {{ name }}
- printf placeholders: %s, %d, %(name)s
- brace placeholders: {count}, {name}

Example:
  python scripts/i18n_placeholder_check.py
  python scripts/i18n_placeholder_check.py --langs de es fr bg --show 20
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from babel.messages import pofile

PLACEHOLDER_RE = re.compile(
    r"(\{\{[^{}]+\}\}"  # Jinja placeholders
    r"|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf named
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf positional
    r"|\{[a-zA-Z0-9_:.!-]+\})"  # python/braced placeholders, simple form
)


@dataclass
class Mismatch:
    lang: str
    source_preview: str
    translated_preview: str
    expected: list[str]
    actual: list[str]
    refs: list[str]
    plural_index: int | None = None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--translations-dir", default="translations")
    ap.add_argument("--domain", default="messages")
    ap.add_argument("--langs", nargs="*", default=[])
    ap.add_argument("--show", type=int, default=25, help="Show up to N mismatches total")
    ap.add_argument("--per-lang", type=int, default=5, help="Show up to N mismatches per locale in summary")
    return ap.parse_args()


def normalize_ph(ph: str) -> str:
    if ph.startswith("{{") and ph.endswith("}}"):
        inner = ph[2:-2].strip()
        inner = re.sub(r"\s+", " ", inner)
        return "{{ " + inner + " }}"
    return ph


def extract_placeholders(text: str) -> list[str]:
    if not text:
        return []
    return sorted({normalize_ph(m.group(0)) for m in PLACEHOLDER_RE.finditer(text)})


def load_catalog(po_path: Path, locale: str):
    with po_path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def iter_locale_dirs(root: Path) -> Iterable[Path]:
    for p in sorted(root.iterdir()):
        if p.is_dir():
            yield p


def _preview(s: str, limit: int = 110) -> str:
    t = (s or "").replace("\n", "\\n")
    if len(t) > limit:
        return t[: limit - 3] + "..."
    return t


def _refs(msg) -> list[str]:
    locs = getattr(msg, "locations", None) or []
    return [f"{path}:{line}" for (path, line) in locs]


def _plural_forms(msg) -> list[tuple[int | None, str, str]]:
    """
    Returns tuples of (plural_index, source_text, translated_text).
    For singular messages plural_index is None.
    For plural messages:
      index 0 compares against singular source
      indexes >0 compare against plural source
    """
    if isinstance(msg.id, str):
        translated = msg.string if isinstance(msg.string, str) else ""
        return [(None, msg.id, translated or "")]

    # Plural msgid tuple/list
    src_singular = str(msg.id[0]) if len(msg.id) > 0 else ""
    src_plural = str(msg.id[1]) if len(msg.id) > 1 else src_singular

    s = msg.string
    out: list[tuple[int | None, str, str]] = []
    if isinstance(s, dict):
        for idx in sorted(s.keys()):
            src = src_singular if idx == 0 else src_plural
            out.append((idx, src, str(s.get(idx) or "")))
        return out
    if isinstance(s, (tuple, list)):
        for idx, val in enumerate(s):
            src = src_singular if idx == 0 else src_plural
            out.append((idx, src, str(val or "")))
        return out

    # Fallback unexpected structure
    return [(0, src_singular, str(s or ""))]


def find_mismatches_for_locale(po_path: Path, lang: str) -> list[Mismatch]:
    cat = load_catalog(po_path, lang)
    mismatches: list[Mismatch] = []

    for msg in cat:
        if not msg.id or msg.id == "" or getattr(msg, "obsolete", False):
            continue

        for pidx, src_text, tr_text in _plural_forms(msg):
            # Skip empty translations: coverage script handles those
            if not (tr_text or "").strip():
                continue

            expected = extract_placeholders(src_text)
            actual = extract_placeholders(tr_text)
            if expected != actual:
                mismatches.append(
                    Mismatch(
                        lang=lang,
                        source_preview=_preview(src_text),
                        translated_preview=_preview(tr_text),
                        expected=expected,
                        actual=actual,
                        refs=_refs(msg),
                        plural_index=pidx,
                    )
                )

    return mismatches


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = parse_args()
    root = Path(args.translations_dir)
    if not root.exists():
        raise SystemExit(f"Translations dir not found: {root}")

    if args.langs:
        locale_dirs = [root / lang for lang in args.langs]
    else:
        locale_dirs = list(iter_locale_dirs(root))

    all_mismatches: list[Mismatch] = []
    by_lang: dict[str, list[Mismatch]] = {}

    for loc_dir in locale_dirs:
        lang = loc_dir.name
        po_path = loc_dir / "LC_MESSAGES" / f"{args.domain}.po"
        if not po_path.exists():
            continue
        mismatches = find_mismatches_for_locale(po_path, lang)
        by_lang[lang] = mismatches
        all_mismatches.extend(mismatches)

    print("\n=== i18n placeholder mismatch report ===\n")
    print("By locale (lower is better):")
    for lang, items in sorted(by_lang.items(), key=lambda kv: len(kv[1])):
        print(f"- {lang}: {len(items)} mismatch(es)")

    if not all_mismatches:
        print("\nNo placeholder mismatches found.")
        return 0

    print(f"\nShowing up to {args.show} mismatches total:\n")

    shown_total = 0
    for lang, items in sorted(by_lang.items(), key=lambda kv: len(kv[1]), reverse=True):
        if not items:
            continue
        print(f"[{lang}] total={len(items)}")
        for m in items[: args.per_lang]:
            if shown_total >= args.show:
                break
            idx_label = "" if m.plural_index is None else f" (plural idx {m.plural_index})"
            print(f"  - source{idx_label}: {m.source_preview}")
            print(f"    translated: {m.translated_preview}")
            print(f"    expected: {m.expected}")
            print(f"    actual:   {m.actual}")
            if m.refs:
                print(f"    refs:     {', '.join(m.refs[:3])}")
            shown_total += 1
        print()
        if shown_total >= args.show:
            break

    print("Tip: fix placeholders first, then compile: .venv\\Scripts\\pybabel.exe compile -d translations")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
