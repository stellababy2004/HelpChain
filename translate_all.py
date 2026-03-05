#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-translate gettext .po catalogs.

Source of truth:
  translations/fr/LC_MESSAGES/messages.po

Examples:
  python translate_all.py --provider deepl --api-key %DEEPL_API_KEY% --source-lang fr --target-langs en,bg --root translations --compile
  python translate_all.py --provider google --api-key %GOOGLE_API_KEY% --source-lang fr --target-langs en,bg --root translations --compile
  python translate_all.py --provider libretranslate --base-url http://localhost:5000 --source-lang fr --target-langs en,bg --root translations --compile
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import polib
import requests


# Placeholder patterns to protect from machine translation
RE_PRINTF = re.compile(r"%\([A-Za-z0-9_]+\)[sdfox]")
RE_PERCENT = re.compile(r"%(?:\d+\$)?[sdfox]")
RE_BRACES = re.compile(r"\{[A-Za-z0-9_.-]+\}")
RE_JINJA = re.compile(r"(\{\{.*?\}\}|\{%.+?%\})", re.DOTALL)
RE_HTMLTAG = re.compile(r"</?[^>]+?>")
RE_URL = re.compile(r"https?://\S+")
RE_EMAIL = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")


def protect_text(text: str) -> Tuple[str, List[str]]:
    placeholders: List[str] = []

    def _repl(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"__PH{len(placeholders)-1}__"

    for regex in (RE_JINJA, RE_PRINTF, RE_PERCENT, RE_BRACES, RE_HTMLTAG, RE_URL, RE_EMAIL):
        text = regex.sub(_repl, text)
    return text, placeholders


def restore_text(text: str, placeholders: List[str]) -> str:
    for i, ph in enumerate(placeholders):
        text = text.replace(f"__PH{i}__", ph)
    return text


def looks_like_code_or_key(s: str) -> bool:
    stripped = s.strip()
    if not stripped:
        return True
    if re.fullmatch(r"[A-Za-z0-9_.:-]+", stripped):
        return True
    if "/" in stripped and " " not in stripped:
        return True
    return False


@dataclass
class ProviderConfig:
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class Translator:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.session = requests.Session()

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if self.cfg.provider == "deepl":
            return self._deepl(text, source_lang, target_lang)
        if self.cfg.provider == "google":
            return self._google(text, source_lang, target_lang)
        if self.cfg.provider == "libretranslate":
            return self._libretranslate(text, source_lang, target_lang)
        raise ValueError(f"Unknown provider: {self.cfg.provider}")

    def _deepl(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self.cfg.api_key:
            raise ValueError("DeepL requires --api-key")
        url = "https://api-free.deepl.com/v2/translate"
        headers = {"Authorization": f"DeepL-Auth-Key {self.cfg.api_key}"}
        data = {
            "text": text,
            "source_lang": source_lang.upper(),
            "target_lang": target_lang.upper(),
        }
        res = self.session.post(url, headers=headers, data=data, timeout=30)
        res.raise_for_status()
        return res.json()["translations"][0]["text"]

    def _google(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self.cfg.api_key:
            raise ValueError("Google requires --api-key")
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {
            "key": self.cfg.api_key,
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        res = self.session.post(url, params=params, timeout=30)
        res.raise_for_status()
        return res.json()["data"]["translations"][0]["translatedText"]

    def _libretranslate(self, text: str, source_lang: str, target_lang: str) -> str:
        base = (self.cfg.base_url or "http://localhost:5000").rstrip("/")
        payload = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if self.cfg.api_key:
            payload["api_key"] = self.cfg.api_key
        res = self.session.post(f"{base}/translate", json=payload, timeout=30)
        res.raise_for_status()
        return res.json()["translatedText"]


def po_path(root: Path, lang: str) -> Path:
    return root / lang / "LC_MESSAGES" / "messages.po"


def load_cache(cache_file: Path) -> dict:
    if not cache_file.exists():
        return {}
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_cache(cache_file: Path, cache: dict) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_target_po(source_po: Path, target_po: Path, lang: str) -> None:
    target_po.parent.mkdir(parents=True, exist_ok=True)
    if target_po.exists():
        return

    src = polib.pofile(str(source_po))
    dst = polib.POFile()
    dst.metadata = dict(src.metadata)
    if "Language" in dst.metadata:
        dst.metadata["Language"] = lang

    for e in src:
        ne = polib.POEntry(
            msgid=e.msgid,
            msgid_plural=e.msgid_plural,
            msgstr="" if not e.msgid_plural else "",
            msgstr_plural={} if e.msgid_plural else None,
            occurrences=list(e.occurrences),
            comment=e.comment,
            tcomment=e.tcomment,
            flags=set(e.flags),
            previous_msgid=e.previous_msgid,
            previous_msgid_plural=e.previous_msgid_plural,
            linenum=e.linenum,
            obsolete=e.obsolete,
        )
        if e.msgid_plural:
            ne.msgstr_plural = {k: "" for k in e.msgstr_plural.keys()} if e.msgstr_plural else {0: "", 1: ""}
        dst.append(ne)

    dst.save(str(target_po))


def translate_po(
    source_po: Path,
    target_po: Path,
    translator: Translator,
    source_lang: str,
    target_lang: str,
    include_fuzzy: bool,
    dry_run: bool,
    sleep_s: float,
    cache: dict | None = None,
) -> Tuple[int, int]:
    src = polib.pofile(str(source_po))
    dst = polib.pofile(str(target_po))
    src_map = {e.msgid: e for e in src}

    translated = 0
    skipped = 0

    for entry in dst:
        if entry.obsolete or entry.msgid == "":
            skipped += 1
            continue

        is_fuzzy = "fuzzy" in entry.flags
        if entry.msgid_plural:
            plural_map = entry.msgstr_plural or {}
            needs = any(not plural_map.get(k, "").strip() for k in plural_map.keys()) or not plural_map
        else:
            needs = not entry.msgstr.strip()

        if not needs and not (include_fuzzy and is_fuzzy):
            skipped += 1
            continue

        src_entry = src_map.get(entry.msgid)
        base_text = src_entry.msgid if src_entry else entry.msgid
        if looks_like_code_or_key(base_text):
            skipped += 1
            continue

        protected, placeholders = protect_text(base_text)
        cache_key = f"{source_lang}|{target_lang}|{protected}"
        if cache is not None and cache_key in cache:
            out = restore_text(cache[cache_key], placeholders).strip()
        else:
            try:
                translated = translator.translate(protected, source_lang=source_lang, target_lang=target_lang)
                if cache is not None:
                    cache[cache_key] = translated
                out = restore_text(translated, placeholders).strip()
            except Exception as ex:  # noqa: BLE001
                print(f"[WARN] {target_lang}: failed msgid={entry.msgid!r}: {ex}", file=sys.stderr)
                skipped += 1
                continue

        if entry.msgid_plural:
            if entry.msgstr_plural is None:
                entry.msgstr_plural = {0: "", 1: ""}
            for k in list(entry.msgstr_plural.keys()):
                if not entry.msgstr_plural.get(k, "").strip() or (include_fuzzy and is_fuzzy):
                    entry.msgstr_plural[k] = out
        else:
            entry.msgstr = out

        if "fuzzy" in entry.flags:
            entry.flags.remove("fuzzy")

        translated += 1
        if sleep_s > 0:
            time.sleep(sleep_s)

    if not dry_run:
        dst.save(str(target_po))
    return translated, skipped


def compile_mo(root: Path, langs: Iterable[str]) -> None:
    for lang in langs:
        po = po_path(root, lang)
        if not po.exists():
            continue
        catalog = polib.pofile(str(po))
        catalog.save_as_mofile(str(po.with_suffix(".mo")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="translations")
    parser.add_argument("--source-lang", default="fr")
    parser.add_argument("--target-langs", required=True, help="comma separated, e.g. en,bg,es")
    parser.add_argument("--provider", choices=["deepl", "google", "libretranslate"], required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--include-fuzzy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--cache-file", default="translations/.translation_cache.json")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    src_po = po_path(root, args.source_lang)
    if not src_po.exists():
        print(f"[ERROR] Source PO not found: {src_po}", file=sys.stderr)
        return 2

    langs = [x.strip() for x in args.target_langs.split(",") if x.strip()]
    langs = [x for x in langs if x != args.source_lang]
    if not langs:
        print("[ERROR] No target languages after filtering source language.", file=sys.stderr)
        return 2

    translator = Translator(ProviderConfig(provider=args.provider, api_key=args.api_key, base_url=args.base_url))
    cache_file = Path(args.cache_file)
    cache = {} if args.no_cache else load_cache(cache_file)

    total_t = 0
    total_s = 0
    for lang in langs:
        tpo = po_path(root, lang)
        ensure_target_po(src_po, tpo, lang)
        translated, skipped = translate_po(
            source_po=src_po,
            target_po=tpo,
            translator=translator,
            source_lang=args.source_lang,
            target_lang=lang,
            include_fuzzy=args.include_fuzzy,
            dry_run=args.dry_run,
            sleep_s=args.sleep,
            cache=cache,
        )
        total_t += translated
        total_s += skipped
        print(f"[OK] {lang}: translated={translated} skipped={skipped} -> {tpo}")

    if not args.no_cache and not args.dry_run:
        save_cache(cache_file, cache)
        print(f"[OK] Cache saved: {cache_file}")

    if args.compile and not args.dry_run:
        compile_mo(root, langs)
        print("[OK] Compiled .mo files.")

    print(f"[DONE] total translated={total_t} total skipped={total_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
