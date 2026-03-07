#!/usr/bin/env python3
"""
HelpChain - Free local Babel .po auto-translation (FR -> EN/DE/BG)

Usage:
  1) Install deps:
     pip install polib transformers sentencepiece torch

  2) Dry-run (no file writes):
     python scripts/auto_translate_po.py --dry-run

  3) Write missing translations:
     python scripts/auto_translate_po.py --write

  4) Compile Babel catalogs:
     pybabel compile -d translations
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import polib
import torch
from transformers import MarianMTModel, MarianTokenizer

BASE_DIR = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = BASE_DIR / "translations"
SOURCE_LOCALE = "fr"
SOURCE_PO = TRANSLATIONS_DIR / SOURCE_LOCALE / "LC_MESSAGES" / "messages.po"

TARGET_MODELS: Dict[str, str] = {
    "en": "Helsinki-NLP/opus-mt-fr-en",
    "de": "Helsinki-NLP/opus-mt-fr-de",
    "bg": "Helsinki-NLP/opus-mt-fr-bg",
}

# Order matters: keep more specific patterns first.
PLACEHOLDER_RE = re.compile(
    r"(\{\{\s*[^{}]+\s*\}\}"  # Jinja: {{ variable }}
    r"|%\([^)]+\)[#0\- +]?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrs]"  # %(name)s
    r"|%(?!%)[#0\- +]?(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrs]"  # %s
    r"|\{[A-Za-z_][A-Za-z0-9_]*\}"  # {name}
    r"|&[A-Za-z0-9#]+;)"  # HTML entity
)


@dataclass
class Stats:
    scanned: int = 0
    already_translated: int = 0
    autofilled: int = 0
    skipped_obsolete: int = 0
    skipped_empty: int = 0
    skipped_fuzzy: int = 0
    skipped_missing_in_target: int = 0


class LocalMarianTranslator:
    def __init__(self, model_name: str) -> None:
        self.tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.model = MarianMTModel.from_pretrained(model_name)
        self.model.eval()
        self.device = "cpu"
        self.model.to(self.device)

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        if not texts:
            return []
        with torch.no_grad():
            encoded = self.tokenizer(
                list(texts),
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            generated = self.model.generate(
                **encoded,
                max_length=512,
                num_beams=4,
            )
            return [
                self.tokenizer.decode(t, skip_special_tokens=True).strip()
                for t in generated
            ]


def mask_placeholders(text: str) -> Tuple[str, Dict[str, str]]:
    replacements: Dict[str, str] = {}
    idx = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal idx
        token = f"__HC_PH_{idx:03d}__"
        replacements[token] = match.group(0)
        idx += 1
        return token

    return PLACEHOLDER_RE.sub(repl, text), replacements


def unmask_placeholders(text: str, replacements: Dict[str, str]) -> str:
    restored = text
    for token, original in replacements.items():
        restored = restored.replace(token, original)
    return restored


def is_effectively_empty(text: str | None) -> bool:
    return not (text or "").strip()


def source_text_for_entry(entry: polib.POEntry) -> str:
    # FR canonical source: prefer msgstr when present; else fallback to msgid.
    msgstr = (entry.msgstr or "").strip()
    if msgstr:
        return msgstr
    return (entry.msgid or "").strip()


def iter_chunks(items: Sequence[Tuple[polib.POEntry, str]], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def process_locale(
    locale: str,
    source_po: polib.POFile,
    target_path: Path,
    translator: LocalMarianTranslator,
    dry_run: bool,
    batch_size: int,
    skip_fuzzy: bool,
) -> Stats:
    stats = Stats()
    target_po = polib.pofile(str(target_path))
    target_by_id = {e.msgid: e for e in target_po if e.msgid}

    to_translate: List[Tuple[polib.POEntry, str]] = []

    for src_entry in source_po:
        stats.scanned += 1
        if src_entry.obsolete:
            stats.skipped_obsolete += 1
            continue
        msgid = (src_entry.msgid or "").strip()
        if not msgid:
            stats.skipped_empty += 1
            continue

        src_text = source_text_for_entry(src_entry)
        if is_effectively_empty(src_text):
            stats.skipped_empty += 1
            continue

        dst_entry = target_by_id.get(msgid)
        if dst_entry is None:
            stats.skipped_missing_in_target += 1
            continue
        if dst_entry.obsolete:
            stats.skipped_obsolete += 1
            continue
        if not is_effectively_empty(dst_entry.msgstr):
            stats.already_translated += 1
            continue
        if skip_fuzzy and "fuzzy" in dst_entry.flags:
            stats.skipped_fuzzy += 1
            continue

        to_translate.append((dst_entry, src_text))

    for chunk in iter_chunks(to_translate, batch_size):
        prepared: List[str] = []
        masks: List[Dict[str, str]] = []
        entries: List[polib.POEntry] = []

        for entry, src_text in chunk:
            masked_text, replacement_map = mask_placeholders(src_text)
            prepared.append(masked_text)
            masks.append(replacement_map)
            entries.append(entry)

        translated = translator.translate_batch(prepared)

        for entry, translated_text, replacement_map in zip(entries, translated, masks):
            cleaned = unmask_placeholders(translated_text, replacement_map).strip()
            if is_effectively_empty(cleaned):
                continue
            if not dry_run:
                entry.msgstr = cleaned
            stats.autofilled += 1

    if not dry_run:
        target_po.save(str(target_path))

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-translate missing Babel .po entries from FR to EN/DE/BG with local MarianMT."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write .po files.")
    parser.add_argument("--write", action="store_true", help="Write missing translations into target .po files.")
    parser.add_argument("--batch-size", type=int, default=16, help="Translation batch size (default: 16).")
    parser.add_argument(
        "--include-fuzzy",
        action="store_true",
        help="Also translate fuzzy entries with empty msgstr (default: skip fuzzy).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run or not args.write
    skip_fuzzy = not args.include_fuzzy

    if not SOURCE_PO.exists():
        print(f"[error] Source catalog not found: {SOURCE_PO}")
        return 1

    source_po = polib.pofile(str(SOURCE_PO))
    print(f"[info] Source: {SOURCE_PO}")
    print(f"[info] Mode: {'dry-run' if dry_run else 'write'}")
    print(f"[info] Batch size: {args.batch_size}")
    print(f"[info] Skip fuzzy: {skip_fuzzy}")

    reports: Dict[str, Stats] = {}
    for locale, model_name in TARGET_MODELS.items():
        target_path = TRANSLATIONS_DIR / locale / "LC_MESSAGES" / "messages.po"
        if not target_path.exists():
            print(f"[warn] Missing target catalog for {locale}: {target_path} (skipped)")
            continue

        print(f"\n[locale:{locale}] Loading model: {model_name}")
        translator = LocalMarianTranslator(model_name=model_name)
        reports[locale] = process_locale(
            locale=locale,
            source_po=source_po,
            target_path=target_path,
            translator=translator,
            dry_run=dry_run,
            batch_size=max(1, args.batch_size),
            skip_fuzzy=skip_fuzzy,
        )

    print("\n=== Auto-translation report ===")
    for locale in sorted(reports.keys()):
        s = reports[locale]
        print(
            f"{locale}: scanned={s.scanned} "
            f"already_translated={s.already_translated} "
            f"autofilled={s.autofilled} "
            f"skipped_empty={s.skipped_empty} "
            f"skipped_obsolete={s.skipped_obsolete} "
            f"skipped_fuzzy={s.skipped_fuzzy} "
            f"skipped_missing_in_target={s.skipped_missing_in_target}"
        )

    if dry_run:
        print("\n[done] Dry-run complete. No files were modified.")
    else:
        print("\n[done] Write complete. Run: pybabel compile -d translations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
