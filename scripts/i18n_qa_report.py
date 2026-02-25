#!/usr/bin/env python3
"""
QA report for gettext translations across locales.

Reports:
- coverage ranking by locale
- missing msgstr counts
- suspect translations (msgstr identical to msgid)

Example:
  python scripts/i18n_qa_report.py
  python scripts/i18n_qa_report.py --langs fr en de es --top-suspect 15
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from babel.messages import pofile


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--translations-dir", default="translations")
    ap.add_argument("--domain", default="messages")
    ap.add_argument("--langs", nargs="*", default=[])
    ap.add_argument("--top-suspect", type=int, default=8)
    ap.add_argument("--show-suspect", action="store_true", help="Print suspect examples per locale")
    return ap.parse_args()


@dataclass
class LocaleStats:
    lang: str
    total: int = 0
    empty: int = 0
    filled: int = 0
    identical: int = 0
    plural_total: int = 0
    errors: int = 0
    suspects: list[tuple[str, list[str]]] | None = None

    @property
    def coverage(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.filled / self.total) * 100.0


def iter_locale_dirs(root: Path) -> Iterable[Path]:
    for p in sorted(root.iterdir()):
        if p.is_dir():
            yield p


def load_catalog(po_path: Path, locale: str):
    with po_path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def _string_nonempty(v) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (tuple, list)):
        return any((x or "").strip() for x in v)
    if isinstance(v, dict):
        return any((x or "").strip() for x in v.values())
    return False


def _normalize_text(v) -> str:
    return " ".join((v or "").split()).strip()


def _looks_translatable_text(s: str) -> bool:
    if not s:
        return False
    # Ignore placeholders/markup-ish fragments where equality is less meaningful.
    if "{" in s or "}" in s or "{{" in s or "}}" in s:
        return False
    if s.startswith("/") or s.endswith(".html"):
        return False
    return True


def collect_stats(po_path: Path, lang: str, top_suspect: int) -> LocaleStats:
    stats = LocaleStats(lang=lang, suspects=[])
    catalog = load_catalog(po_path, lang)

    for msg in catalog:
        if not msg.id or msg.id == "" or getattr(msg, "obsolete", False):
            continue

        stats.total += 1
        if isinstance(msg.id, (tuple, list)):
            stats.plural_total += 1

        if not _string_nonempty(msg.string):
            stats.empty += 1
            continue

        stats.filled += 1

        # Suspect: exact same translation as source text (common machine-miss or untranslated string)
        if isinstance(msg.id, str) and isinstance(msg.string, str):
            src = _normalize_text(msg.id)
            dst = _normalize_text(msg.string)
            if src and dst and src == dst and _looks_translatable_text(src):
                stats.identical += 1
                if len(stats.suspects or []) < top_suspect:
                    refs = [str(r) for r in (getattr(msg, "locations", None) or [])]
                    stats.suspects.append((src, refs))

    return stats


def format_refs(refs: list[str]) -> str:
    if not refs:
        return "(no refs)"
    return ", ".join(refs[:3])


def main() -> int:
    args = parse_args()
    root = Path(args.translations_dir)
    if not root.exists():
        raise SystemExit(f"Translations dir not found: {root}")

    if args.langs:
        locale_dirs = [root / lang for lang in args.langs]
    else:
        locale_dirs = list(iter_locale_dirs(root))

    results: list[LocaleStats] = []
    for loc_dir in locale_dirs:
        lang = loc_dir.name
        po_path = loc_dir / "LC_MESSAGES" / f"{args.domain}.po"
        if not po_path.exists():
            continue
        try:
            stats = collect_stats(po_path, lang, args.top_suspect)
            results.append(stats)
        except Exception as e:
            results.append(LocaleStats(lang=lang, errors=1, suspects=[]))
            print(f"[ERROR] {lang}: {e}")

    results.sort(key=lambda r: (r.coverage, -r.empty), reverse=True)

    print("\n=== i18n QA report ===\n")
    print("Coverage ranking (higher is better):")
    print("lang   coverage   filled/total   empty   identical   plural")
    for r in results:
        print(
            f"{r.lang:<5} {r.coverage:>7.1f}%   {r.filled:>4}/{r.total:<4}   "
            f"{r.empty:>4}   {r.identical:>8}   {r.plural_total:>6}"
        )

    print("\nTop missing (most empty msgstr):")
    for r in sorted(results, key=lambda x: x.empty, reverse=True)[:10]:
        print(f"- {r.lang}: empty={r.empty}, coverage={r.coverage:.1f}%")

    print("\nTop suspect identical translations (msgstr == msgid):")
    for r in sorted(results, key=lambda x: x.identical, reverse=True)[:10]:
        print(f"- {r.lang}: identical={r.identical}, coverage={r.coverage:.1f}%")

    if args.show_suspect:
        print("\nSuspect examples:")
        for r in sorted(results, key=lambda x: x.identical, reverse=True):
            if not r.suspects:
                continue
            print(f"\n[{r.lang}] identical={r.identical}")
            for text, refs in r.suspects[: args.top_suspect]:
                preview = text.replace("\n", "\\n")
                if len(preview) > 100:
                    preview = preview[:97] + "..."
                print(f"  - {preview}")
                print(f"    refs: {format_refs(refs)}")

    print("\nTip: after edits, run: .venv\\Scripts\\pybabel.exe compile -d translations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
