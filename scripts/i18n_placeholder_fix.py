#!/usr/bin/env python3
"""
Auto-fix placeholder artifacts in gettext PO files caused by MT tools.

Current focus:
- restores Argos-style placeholder artifacts like "HC PH 0" back to the
  source placeholders (%(id)s, %(days)s, {count}, {{ name }}) by index.

Example:
  python scripts/i18n_placeholder_fix.py --langs de es bg fr --dry-run
  python scripts/i18n_placeholder_fix.py --langs de es bg fr
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from babel.messages import pofile


PLACEHOLDER_RE = re.compile(
    r"(\{\{[^{}]+\}\}"  # Jinja placeholders
    r"|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf named
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf positional
    r"|\{[a-zA-Z0-9_:.!-]+\})"  # brace placeholders
)

# Argos artifact variants observed after translating "__HC_PH_0__":
# "HC PH 0", "HC_PH_0", "__HC PH 0__", etc.
HC_PH_ARTIFACT_RE = re.compile(
    r"(?i)(?:__\s*)?hc(?:\s+|_)*ph(?:\s+|_)*(\d+)(?:\s*__)?"
)


@dataclass
class Stats:
    scanned: int = 0
    changed_entries: int = 0
    replacements: int = 0
    unresolved: int = 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--translations-dir", default="translations")
    ap.add_argument("--domain", default="messages")
    ap.add_argument("--langs", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args()


def iter_locale_dirs(root: Path) -> Iterable[Path]:
    for p in sorted(root.iterdir()):
        if p.is_dir():
            yield p


def load_catalog(po_path: Path, locale: str):
    with po_path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def save_catalog(po_path: Path, catalog) -> None:
    with po_path.open("wb") as f:
        pofile.write_po(f, catalog, width=120)


def extract_placeholders(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(0) for m in PLACEHOLDER_RE.finditer(text)]


def source_text_for_plural(msg, idx: int) -> str:
    if isinstance(msg.id, str):
        return msg.id
    if idx == 0:
        return str(msg.id[0]) if len(msg.id) > 0 else ""
    return str(msg.id[1]) if len(msg.id) > 1 else str(msg.id[0])


def repair_text(source_text: str, translated_text: str) -> tuple[str, int, int]:
    """
    Returns (new_text, replacements_made, unresolved_artifacts_remaining)
    """
    if not translated_text:
        return translated_text, 0, 0

    source_phs = extract_placeholders(source_text)
    if not source_phs:
        return translated_text, 0, 0

    replacements = 0

    def repl(match: re.Match) -> str:
        nonlocal replacements
        raw_idx = match.group(1)
        try:
            idx = int(raw_idx)
        except Exception:
            return match.group(0)
        if 0 <= idx < len(source_phs):
            replacements += 1
            return source_phs[idx]
        return match.group(0)

    new_text = HC_PH_ARTIFACT_RE.sub(repl, translated_text)
    unresolved = len(HC_PH_ARTIFACT_RE.findall(new_text))
    return new_text, replacements, unresolved


def process_msg(msg, verbose: bool) -> tuple[bool, int, int]:
    """
    Returns (changed, replacements, unresolved)
    """
    changed = False
    total_repl = 0
    total_unresolved = 0

    if isinstance(msg.id, str):
        if not isinstance(msg.string, str):
            return False, 0, 0
        new_text, repl_count, unresolved = repair_text(msg.id, msg.string)
        if repl_count and new_text != msg.string:
            if verbose:
                print(f"  fixed: {msg.id[:80]!r}  (+{repl_count})")
            msg.string = new_text
            changed = True
        total_repl += repl_count
        total_unresolved += unresolved
        return changed, total_repl, total_unresolved

    # plural forms
    if isinstance(msg.string, dict):
        new_map = dict(msg.string)
        for idx, val in list(new_map.items()):
            src = source_text_for_plural(msg, int(idx))
            new_text, repl_count, unresolved = repair_text(src, str(val or ""))
            if repl_count and new_text != val:
                new_map[idx] = new_text
                changed = True
                if verbose:
                    print(f"  fixed plural idx {idx}: {str(msg.id[0])[:80]!r}  (+{repl_count})")
            total_repl += repl_count
            total_unresolved += unresolved
        if changed:
            msg.string = new_map
        return changed, total_repl, total_unresolved

    if isinstance(msg.string, (tuple, list)):
        new_vals = list(msg.string)
        for idx, val in enumerate(new_vals):
            src = source_text_for_plural(msg, idx)
            new_text, repl_count, unresolved = repair_text(src, str(val or ""))
            if repl_count and new_text != val:
                new_vals[idx] = new_text
                changed = True
                if verbose:
                    print(f"  fixed plural idx {idx}: {str(msg.id[0])[:80]!r}  (+{repl_count})")
            total_repl += repl_count
            total_unresolved += unresolved
        if changed:
            msg.string = tuple(new_vals) if isinstance(msg.string, tuple) else new_vals
        return changed, total_repl, total_unresolved

    return False, 0, 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = parse_args()
    root = Path(args.translations_dir)
    locale_dirs = [root / l for l in args.langs] if args.langs else list(iter_locale_dirs(root))

    grand = Stats()
    for loc_dir in locale_dirs:
        lang = loc_dir.name
        po_path = loc_dir / "LC_MESSAGES" / f"{args.domain}.po"
        if not po_path.exists():
            continue
        cat = load_catalog(po_path, lang)
        stats = Stats()

        print(f"[{lang}] {po_path}")
        for msg in cat:
            if not msg.id or msg.id == "" or getattr(msg, "obsolete", False):
                continue
            stats.scanned += 1
            changed, repl_count, unresolved = process_msg(msg, args.verbose)
            if changed:
                stats.changed_entries += 1
            stats.replacements += repl_count
            stats.unresolved += unresolved

        print(
            f"  scanned={stats.scanned} changed_entries={stats.changed_entries} "
            f"replacements={stats.replacements} unresolved={stats.unresolved}"
        )

        if not args.dry_run and stats.changed_entries:
            save_catalog(po_path, cat)

        grand.scanned += stats.scanned
        grand.changed_entries += stats.changed_entries
        grand.replacements += stats.replacements
        grand.unresolved += stats.unresolved

    print(
        "\nSummary: "
        f"scanned={grand.scanned} changed_entries={grand.changed_entries} "
        f"replacements={grand.replacements} unresolved={grand.unresolved}"
    )
    if args.dry_run:
        print("Dry run only (no files written).")
    else:
        print("Done. Re-run placeholder checker, then compile: .venv\\Scripts\\pybabel.exe compile -d translations")
    return 0 if grand.unresolved == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
