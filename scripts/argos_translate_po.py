#!/usr/bin/env python
"""
Offline gettext PO translation helper using Argos Translate.

Safe defaults:
- translates only empty msgstr entries
- preserves common placeholders ({count}, %s, {{ jinja }})
- can reuse an existing source locale catalog (e.g. fr) as source text

Example:
  .venv\\Scripts\\python.exe scripts\\argos_translate_po.py --targets es de it --source-locale fr
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from babel.messages import pofile


LANG_CODE_MAP = {
    "no": "nb",  # Argos packages often use nb rather than no
}

PLACEHOLDER_RE = re.compile(
    r"(\{\{[^{}]+\}\}"  # Jinja placeholders
    r"|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf named
    r"|%[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"  # printf positional
    r"|\{[a-zA-Z0-9_:.!-]+\})"  # python/braced placeholders, simple form
)


@dataclass
class Stats:
    scanned: int = 0
    translated: int = 0
    skipped_filled: int = 0
    skipped_fuzzy: int = 0
    errors: int = 0


def _configure_stdio_utf8() -> None:
    # Windows consoles often default to cp1252 and crash on Cyrillic/emoji logs.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Translate gettext PO files using Argos Translate (offline).")
    p.add_argument("--translations-dir", default="translations", help="Translations root directory")
    p.add_argument("--domain", default="messages", help="gettext domain filename (without .po)")
    p.add_argument("--source-locale", default="fr", help="Catalog to use as source text fallback (default: fr)")
    p.add_argument(
        "--targets",
        nargs="*",
        default=[],
        help="Target locale codes (space-separated). If omitted, use all locale dirs except source locale.",
    )
    p.add_argument("--overwrite", action="store_true", help="Overwrite non-empty msgstr values too")
    p.add_argument(
        "--overwrite-identical-only",
        action="store_true",
        help="Overwrite only entries where msgstr is identical to msgid (safe cleanup pass)",
    )
    p.add_argument("--skip-fuzzy", action="store_true", help="Skip fuzzy entries")
    p.add_argument("--max-messages", type=int, default=0, help="Stop after N translated messages per locale (0 = no limit)")
    p.add_argument("--dry-run", action="store_true", help="Do not write files")
    p.add_argument("--list-installed", action="store_true", help="Print installed Argos languages and exit")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def import_argos():
    try:
        import argostranslate.translate as argos_translate  # type: ignore
    except Exception as e:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Argos Translate is not installed in this environment. "
            "Install locally first: pip install argostranslate"
        ) from e
    return argos_translate


def list_installed_argos(argos_translate) -> None:
    langs = []
    if hasattr(argos_translate, "get_installed_languages"):
        try:
            langs = argos_translate.get_installed_languages()
        except Exception:
            langs = []
    for lang in langs:
        code = getattr(lang, "code", "?")
        name = getattr(lang, "name", "?")
        print(f"{code}\t{name}")
    if not langs:
        print("(no installed Argos languages detected)")


def get_argos_translate_fn(argos_translate, src_code: str, dst_code: str) -> Callable[[str], str]:
    src = LANG_CODE_MAP.get(src_code, src_code)
    dst = LANG_CODE_MAP.get(dst_code, dst_code)

    if hasattr(argos_translate, "get_translation_from_codes"):
        translation = argos_translate.get_translation_from_codes(src, dst)
        return translation.translate

    if hasattr(argos_translate, "translate"):
        return lambda text: argos_translate.translate(text, src, dst)

    raise RuntimeError("Unsupported argostranslate API version: no translation entrypoint found")


def load_catalog(po_path: Path, locale: str):
    with po_path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def save_catalog(po_path: Path, catalog) -> None:
    with po_path.open("wb") as f:
        pofile.write_po(f, catalog, width=120)


def catalog_key(msg) -> Tuple[object, object]:
    return (msg.context, msg.id)


def build_source_map(catalog) -> Dict[Tuple[object, object], object]:
    out: Dict[Tuple[object, object], object] = {}
    for msg in catalog:
      if not msg.id or msg.id == "":
          continue
      out[catalog_key(msg)] = msg
    return out


def is_plural_message(msg) -> bool:
    return isinstance(msg.id, (tuple, list))


def is_empty_translation(msg) -> bool:
    s = msg.string
    if isinstance(s, str):
        return not s.strip()
    if isinstance(s, (tuple, list)):
        return not any((x or "").strip() for x in s)
    if isinstance(s, dict):
        return not any((x or "").strip() for x in s.values())
    return True


def normalize_text(s: str) -> str:
    return " ".join((s or "").split()).strip()


def is_identical_translation(msg) -> bool:
    if isinstance(msg.id, str) and isinstance(msg.string, str):
        src = normalize_text(msg.id)
        dst = normalize_text(msg.string)
        return bool(src) and src == dst
    return False


def mask_placeholders(text: str) -> Tuple[str, List[str]]:
    placeholders: List[str] = []

    def repl(match: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(match.group(0))
        return f"__HC_PH_{idx}__"

    return PLACEHOLDER_RE.sub(repl, text), placeholders


def unmask_placeholders(text: str, placeholders: Sequence[str]) -> str:
    out = text
    for i, ph in enumerate(placeholders):
        out = out.replace(f"__HC_PH_{i}__", ph)
    return out


def translate_text(text: str, translate_fn: Callable[[str], str]) -> str:
    if not text or not text.strip():
        return text

    lines = text.split("\n")
    out_lines: List[str] = []
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        masked, placeholders = mask_placeholders(line)
        translated = translate_fn(masked)
        out_lines.append(unmask_placeholders(translated, placeholders))
    return "\n".join(out_lines)


def pick_source_text(src_msg, target_msg, plural_index: int | None = None) -> str:
    # Prefer source catalog msgstr if present; fallback to msgid.
    if src_msg is not None:
        src_string = src_msg.string
        if plural_index is None:
            if isinstance(src_string, str) and src_string.strip():
                return src_string
        else:
            if isinstance(src_string, (tuple, list)) and len(src_string) > plural_index:
                cand = src_string[plural_index] or ""
                if str(cand).strip():
                    return str(cand)
            if isinstance(src_string, dict):
                cand = src_string.get(plural_index, "") or ""
                if str(cand).strip():
                    return str(cand)

    if plural_index is None:
        return target_msg.id if isinstance(target_msg.id, str) else str(target_msg.id[0])
    if isinstance(target_msg.id, (tuple, list)) and len(target_msg.id) > plural_index:
        return str(target_msg.id[plural_index])
    return str(target_msg.id[0])


def normalize_plural_storage(msg, singular_text: str, plural_text: str):
    s = msg.string
    if isinstance(s, dict):
        keys = sorted(s.keys())
        out = {}
        for idx in keys:
            out[idx] = singular_text if idx == 0 else plural_text
        return out
    if isinstance(s, (tuple, list)):
        count = max(len(s), 2)
        vals = [singular_text if i == 0 else plural_text for i in range(count)]
        return tuple(vals) if isinstance(s, tuple) else vals
    return (singular_text, plural_text)


def translate_catalog(
    target_catalog,
    source_map: Dict[Tuple[object, object], object],
    translate_fn: Callable[[str], str],
    overwrite: bool,
    overwrite_identical_only: bool,
    skip_fuzzy: bool,
    max_messages: int,
    verbose: bool = False,
) -> Stats:
    stats = Stats()

    for msg in target_catalog:
        if not msg.id or msg.id == "":
            continue
        if getattr(msg, "obsolete", False):
            continue

        stats.scanned += 1

        if skip_fuzzy and getattr(msg, "fuzzy", False):
            stats.skipped_fuzzy += 1
            continue

        if not overwrite:
            if is_empty_translation(msg):
                pass
            elif overwrite_identical_only and is_identical_translation(msg):
                pass
            else:
                stats.skipped_filled += 1
                continue

        src_msg = source_map.get(catalog_key(msg))

        try:
            if not is_plural_message(msg):
                source_text = pick_source_text(src_msg, msg)
                translated = translate_text(source_text, translate_fn)
                msg.string = translated
                stats.translated += 1
                if verbose:
                    print(f"  translated: {str(msg.id)[:70]}")
            else:
                singular_source = pick_source_text(src_msg, msg, plural_index=0)
                plural_source = pick_source_text(src_msg, msg, plural_index=1)
                singular_tr = translate_text(singular_source, translate_fn)
                plural_tr = translate_text(plural_source, translate_fn)
                msg.string = normalize_plural_storage(msg, singular_tr, plural_tr)
                stats.translated += 1
                if verbose:
                    print(f"  translated plural: {str(msg.id[0])[:70]}")
        except Exception as e:
            stats.errors += 1
            print(f"  [ERROR] {msg.id!r}: {e}")

        if max_messages and stats.translated >= max_messages:
            break

    return stats


def resolve_targets(translations_dir: Path, source_locale: str, targets_arg: Sequence[str]) -> List[str]:
    if targets_arg:
        return [t.strip() for t in targets_arg if t.strip()]
    return sorted([p.name for p in translations_dir.iterdir() if p.is_dir() and p.name != source_locale])


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()
    translations_dir = Path(args.translations_dir)

    try:
        argos_translate = import_argos()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        print(
            "Then install Argos language packages locally (e.g. fr->es, fr->de, fr->it) and rerun.",
            file=sys.stderr,
        )
        return 2

    if args.list_installed:
        list_installed_argos(argos_translate)
        return 0

    source_po = translations_dir / args.source_locale / "LC_MESSAGES" / f"{args.domain}.po"
    if not source_po.exists():
        print(f"Source catalog not found: {source_po}", file=sys.stderr)
        return 2

    source_catalog = load_catalog(source_po, args.source_locale)
    source_map = build_source_map(source_catalog)
    targets = resolve_targets(translations_dir, args.source_locale, args.targets)
    if not targets:
        print("No target locales found.")
        return 0

    overall_errors = 0
    for target_locale in targets:
        target_po = translations_dir / target_locale / "LC_MESSAGES" / f"{args.domain}.po"
        if not target_po.exists():
            print(f"[SKIP {target_locale}] missing PO file: {target_po}")
            continue

        try:
            translate_fn = get_argos_translate_fn(argos_translate, args.source_locale, target_locale)
        except Exception as e:
            print(f"[SKIP {target_locale}] no Argos package {args.source_locale}->{target_locale}: {e}")
            overall_errors += 1
            continue

        print(f"[{target_locale}] translating {target_po}")
        target_catalog = load_catalog(target_po, target_locale)
        stats = translate_catalog(
            target_catalog,
            source_map,
            translate_fn,
            overwrite=args.overwrite,
            overwrite_identical_only=args.overwrite_identical_only,
            skip_fuzzy=args.skip_fuzzy,
            max_messages=args.max_messages,
            verbose=args.verbose,
        )
        print(
            f"  scanned={stats.scanned} translated={stats.translated} "
            f"skipped_filled={stats.skipped_filled} skipped_fuzzy={stats.skipped_fuzzy} errors={stats.errors}"
        )
        overall_errors += stats.errors

        if not args.dry_run:
            save_catalog(target_po, target_catalog)

    if args.dry_run:
        print("Dry run complete (no files written).")
    else:
        print("Done. Compile translations with: .venv\\Scripts\\pybabel.exe compile -d translations")
    return 0 if overall_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
