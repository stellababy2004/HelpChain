#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict

import requests

EU_LANGS = [
    "en",
    "bg",
    "de",
    "es",
    "it",
    "nl",
    "pt",
    "pl",
    "ro",
    "cs",
    "sk",
    "sl",
    "hr",
    "hu",
    "fi",
    "sv",
    "da",
    "et",
    "lv",
    "lt",
    "mt",
    "ga",
    "el",
]

SOURCE = Path("docs/institutions/source/HelpChain_Overview_FR.md")
SOURCE_FALLBACK = Path("docs/institutions/HelpChain_Overview_FR.md")
TARGET_DIR = Path("docs/institutions/generated")
CACHE_FILE = Path("docs/institutions/.doc_translation_cache.json")

RE_URL = re.compile(r"https?://\S+")
RE_EMAIL = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")


def load_cache() -> Dict[str, str]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: Dict[str, str]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def protect(text: str) -> tuple[str, list[str]]:
    placeholders: list[str] = []

    def _replace(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"__PH{len(placeholders)-1}__"

    for rx in (RE_URL, RE_EMAIL):
        text = rx.sub(_replace, text)
    return text, placeholders


def restore(text: str, placeholders: list[str]) -> str:
    for i, value in enumerate(placeholders):
        text = text.replace(f"__PH{i}__", value)
    return text


def translate_deepl(text: str, target_lang: str) -> str:
    api_key = (os.getenv("DEEPL_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("DEEPL_API_KEY is missing")
    url = "https://api-free.deepl.com/v2/translate"
    headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
    data = {"text": text, "source_lang": "FR", "target_lang": target_lang.upper()}
    res = requests.post(url, headers=headers, data=data, timeout=45)
    res.raise_for_status()
    return res.json()["translations"][0]["text"]


def translate_libre(text: str, target_lang: str) -> str:
    base_url = (os.getenv("LIBRETRANSLATE_URL") or "https://libretranslate.de").rstrip("/")
    payload = {"q": text, "source": "fr", "target": target_lang, "format": "text"}
    api_key = (os.getenv("LIBRETRANSLATE_API_KEY") or "").strip()
    if api_key:
        payload["api_key"] = api_key
    res = requests.post(f"{base_url}/translate", json=payload, timeout=45)
    res.raise_for_status()
    return res.json()["translatedText"]


def translate_text(text: str, target_lang: str) -> str:
    provider = (os.getenv("TRANSLATION_PROVIDER") or "deepl").strip().lower()
    if provider == "deepl":
        return translate_deepl(text, target_lang)
    if provider == "libretranslate":
        return translate_libre(text, target_lang)
    raise RuntimeError(f"Unsupported TRANSLATION_PROVIDER={provider}")


def main() -> int:
    source = SOURCE if SOURCE.exists() else SOURCE_FALLBACK
    if not source.exists():
        print(f"[ERROR] Source file not found: {SOURCE} or {SOURCE_FALLBACK}", file=sys.stderr)
        return 2

    original = source.read_text(encoding="utf-8")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Keep FR master in generated package.
    fr_out = TARGET_DIR / "HelpChain_Overview_FR.md"
    fr_out.write_text(original, encoding="utf-8")

    cache = load_cache()
    provider = (os.getenv("TRANSLATION_PROVIDER") or "deepl").strip().lower()

    for lang in EU_LANGS:
        protected, placeholders = protect(original)
        digest = hashlib.sha256(protected.encode("utf-8")).hexdigest()
        key = f"{provider}|fr|{lang}|{digest}"

        if key in cache:
            translated = cache[key]
            print(f"[CACHE] {lang}")
        else:
            print(f"[TRANSLATE] {lang}")
            translated = translate_text(protected, lang)
            cache[key] = translated

        out = restore(translated, placeholders)
        (TARGET_DIR / f"HelpChain_Overview_{lang.upper()}.md").write_text(out, encoding="utf-8")

    save_cache(cache)
    print(f"[DONE] Generated markdown files in {TARGET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

