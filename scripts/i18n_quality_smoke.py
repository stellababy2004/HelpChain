#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from babel.messages import pofile


CRITICAL_PO_CHECKS = {
    "bg": {
        "Home": "Начало",
        "About": "За нас",
        "Submit a request": "Подайте заявка",
        "My dashboard": "Моето табло",
        "Orienter": "Насочване",
        "Professionnels": "Професионалисти",
        "Search…": "Търсене…",
        "Search": "Търсене",
        "Orienter une demande": "Насочване на заявка",
        "Espace professionnel": "Професионално пространство",
    },
    "en": {
        "Home": "Home",
        "About": "About",
        "Submit a request": "Submit a request",
        "My dashboard": "My dashboard",
        "Orienter": "Orienter",
        "Professionnels": "Professionals",
        "Search…": "Search…",
        "Search": "Search",
        "Orienter une demande": "Orient a request",
        "Espace professionnel": "Professional space",
    },
    "fr": {
        "Home": "Accueil",
        "About": "À propos",
        "Submit a request": "Déposer une demande",
        "Orienter": "Orienter",
        "Professionnels": "Professionnels",
        "Search…": "Rechercher…",
        "Search": "Rechercher",
        "Orienter une demande": "Orienter une demande",
        "Espace professionnel": "Espace professionnel",
    },
    "es": {
        "Home": "Inicio",
        "About": "Acerca de",
        "Submit a request": "Enviar solicitud",
        "Orienter": "Orientar",
        "Professionnels": "Profesionales",
        "Search…": "Buscar…",
        "Search": "Buscar",
        "Orienter une demande": "Orientar una solicitud",
        "Espace professionnel": "Espacio profesional",
    },
    "de": {
        "Home": "Startseite",
        "About": "Über uns",
        "Submit a request": "Anfrage senden",
        "Orienter": "Orientieren",
        "Professionnels": "Fachkräfte",
        "Search…": "Suchen…",
        "Search": "Suchen",
        "Orienter une demande": "Anfrage weiterleiten",
        "Espace professionnel": "Professioneller Bereich",
    },
    "it": {
        "Home": "Home",
        "About": "Chi siamo",
        "Submit a request": "Invia una richiesta",
        "Orienter": "Orienta",
        "Professionnels": "Professionisti",
        "Search…": "Cerca…",
        "Search": "Cerca",
        "Orienter une demande": "Orienta una richiesta",
        "Espace professionnel": "Spazio professionale",
    },
}

DEFAULT_GUARDED_TEMPLATES = [
    "templates/base.html",
    "templates/orienter.html",
    "templates/submit_request.html",
]
EXTENDED_GUARDED_TEMPLATES = DEFAULT_GUARDED_TEMPLATES + [
    "templates/home_new_slim.html",
    "templates/about.html",
    "templates/professionnels.html",
]

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
GREEK_RE = re.compile(r"[\u0370-\u03FF]")
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30FF]")
HAN_RE = re.compile(r"[\u4E00-\u9FFF]")
HANGUL_RE = re.compile(r"[\uAC00-\uD7AF]")
LATIN_RE = re.compile(r"[A-Za-z]")
FRENCH_MARKER_RE = re.compile(r"[àâçéèêëîïôùûüœÀÂÇÉÈÊËÎÏÔÙÛÜŒ]|(?:\b(?:accès|déposer|demande|espace|professionnel|sélectionnez|coordination|conformité)\b)", re.IGNORECASE)
ALL_CAPS_TOKEN_RE = re.compile(r"^[A-Z0-9 .,+()/_-]{1,24}$")
BRAND_ALLOW = {
    "HelpChain",
    "HelpChain.live",
    "KPI",
    "LIVE",
    "RGPD",
    "GDPR",
    "CSV",
    "JSON",
    "PDF",
    "Excel",
    "+359… / +33…",
}
SCRIPT_ALLOWED = {
    "bg": ("cyrillic", "latin"),
    "ru": ("cyrillic", "latin"),
    "uk": ("cyrillic", "latin"),
    "sr": ("cyrillic", "latin"),
    "el": ("greek", "latin"),
    "ar": ("arabic", "latin"),
    "ps": ("arabic", "latin"),
    "he": ("hebrew", "latin"),
    "yi": ("hebrew", "latin"),
    "th": ("thai", "latin"),
    "zh": ("han", "latin"),
    "ja": ("han", "kana", "latin"),
    "ko": ("hangul", "latin"),
}


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Quality smoke for i18n: exact checks for critical navbar/CTA + heuristic checks for all guarded-template strings."
    )
    p.add_argument("--langs", nargs="*", default=["bg", "en", "fr", "es", "de", "it"], help="Locales to check")
    p.add_argument(
        "--warning-only-langs",
        nargs="*",
        default=[],
        help="Locales that should print issues but not fail the process",
    )
    p.add_argument("--translations-dir", default="translations", help="Translations root")
    p.add_argument("--domain", default="messages", help="gettext domain name (without .po)")
    p.add_argument("--show-all", action="store_true", help="Print passing checks too")
    p.add_argument("--templates", nargs="*", default=None, help="Guarded template paths for full-quality checks")
    p.add_argument("--template-profile", choices=["core", "extended"], default="core", help="Guarded template preset")
    p.add_argument("--show-suspects", type=int, default=20, help="Max suspect entries to print per locale")
    return p.parse_args()


def load_catalog(path: Path, locale: str):
    with path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def catalog_map(catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    for msg in catalog:
        if getattr(msg, "obsolete", False):
            continue
        if isinstance(getattr(msg, "id", None), str):
            out[msg.id] = (msg.string or "") if isinstance(msg.string, str) else ""
    return out


def _is_empty_string(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _norm(s: str) -> str:
    return " ".join((s or "").split()).strip()


def _looks_translatable_latin(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    if t in BRAND_ALLOW:
        return False
    if ALL_CAPS_TOKEN_RE.match(t):
        return False
    if len(t) <= 2:
        return False
    if t.startswith("http://") or t.startswith("https://"):
        return False
    if "@" in t and " " not in t:
        return False
    return bool(LATIN_RE.search(t))


def _detect_scripts(text: str) -> set[str]:
    s: set[str] = set()
    if not text:
        return s
    if CYRILLIC_RE.search(text):
        s.add("cyrillic")
    if ARABIC_RE.search(text):
        s.add("arabic")
    if HEBREW_RE.search(text):
        s.add("hebrew")
    if GREEK_RE.search(text):
        s.add("greek")
    if THAI_RE.search(text):
        s.add("thai")
    if HIRAGANA_KATAKANA_RE.search(text):
        s.add("kana")
    if HAN_RE.search(text):
        s.add("han")
    if HANGUL_RE.search(text):
        s.add("hangul")
    if LATIN_RE.search(text):
        s.add("latin")
    return s


def collect_template_quality_issues(catalog, locale: str, templates: set[str], max_examples: int):
    counts = {"empty": 0, "suspect_identical": 0, "foreign_script": 0}
    by_template: dict[str, int] = {}
    examples: list[dict] = []

    for msg in catalog:
        if getattr(msg, "obsolete", False):
            continue
        msgid = getattr(msg, "id", None)
        if not isinstance(msgid, str) or not msgid:
            continue
        msgstr = msg.string if isinstance(msg.string, str) else ""

        refs = []
        for loc in list(getattr(msg, "locations", []) or []):
            if not isinstance(loc, tuple) or not loc:
                continue
            path = str(loc[0]).replace("\\", "/")
            if path in templates:
                line = loc[1] if len(loc) > 1 else "?"
                refs.append(f"{path}:{line}")
        if not refs:
            continue

        first_template = refs[0].split(":", 1)[0]
        reason = None
        if _is_empty_string(msgstr):
            reason = "empty"
        else:
            src = _norm(msgid)
            dst = _norm(msgstr)

            dst_scripts = _detect_scripts(dst)
            src_scripts = _detect_scripts(src)
            allowed_scripts = set(SCRIPT_ALLOWED.get(locale, ("latin",)))

            disallowed_nonlatin = {s for s in (dst_scripts - allowed_scripts) if s != "latin"}
            if disallowed_nonlatin and not (dst_scripts & src_scripts & disallowed_nonlatin):
                # Example: Cyrillic leaked into non-Cyrillic locale, unless source itself uses that script.
                reason = "foreign_script"
            elif locale == "bg":
                # If bg translation equals a Latin source and looks translatable, likely mixed UI text.
                if dst == src and not CYRILLIC_RE.search(src) and _looks_translatable_latin(src):
                    reason = "suspect_identical"
            elif locale != "fr":
                # For non-FR locales, identical French/Cyrillic source is suspicious.
                if dst == src and (CYRILLIC_RE.search(src) or FRENCH_MARKER_RE.search(src)):
                    if src not in BRAND_ALLOW and not ALL_CAPS_TOKEN_RE.match(src):
                        reason = "suspect_identical"
            else:
                # FR locale: flag obvious Cyrillic leakage only.
                if CYRILLIC_RE.search(dst) and not CYRILLIC_RE.search(src):
                    reason = "foreign_script"

        if not reason:
            continue

        counts[reason] += 1
        by_template[first_template] = by_template.get(first_template, 0) + 1
        if len(examples) < max_examples:
            examples.append({"reason": reason, "msgid": msgid, "msgstr": msgstr, "refs": refs})

    return counts, by_template, examples


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()
    root = Path(args.translations_dir)
    warning_only_langs = set(args.warning_only_langs or [])

    failed = 0
    selected_templates = args.templates or (EXTENDED_GUARDED_TEMPLATES if args.template_profile == "extended" else DEFAULT_GUARDED_TEMPLATES)
    templates = {t.replace("\\", "/") for t in selected_templates}
    print("=== i18n quality smoke ===")
    print("Modes: critical exact checks + guarded-template heuristic checks")
    for lang in args.langs:
        checks = CRITICAL_PO_CHECKS.get(lang, {})
        po_path = root / lang / "LC_MESSAGES" / f"{args.domain}.po"
        if not po_path.exists():
            print(f"\n[{lang}] FAIL: missing PO file {po_path}")
            if lang in warning_only_langs:
                print("  Note: warning-only locale; not counted as hard failure.")
            else:
                failed += 1
            continue
        cmap = catalog_map(load_catalog(po_path, lang))
        print(f"\n[{lang}]")
        lang_failed = 0
        critical_failed = 0
        for msgid, expected in checks.items():
            actual = cmap.get(msgid)
            ok = actual == expected
            if ok and not args.show_all:
                continue
            status = "OK" if ok else "FAIL"
            print(f"  {status}: {msgid!r}")
            if not ok:
                print(f"    expected: {expected}")
                print(f"    actual:   {actual!r}")
                lang_failed += 1
                critical_failed += 1

        counts, by_template, examples = collect_template_quality_issues(
            load_catalog(po_path, lang), lang, templates, args.show_suspects
        )
        heuristic_failed = sum(counts.values())
        if heuristic_failed:
            print("  Heuristic issues (guarded templates):")
            print(
                "    counts: "
                + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
            )
            if by_template:
                print("    by template:")
                for file_ref, count in sorted(by_template.items(), key=lambda kv: (-kv[1], kv[0])):
                    print(f"    - {file_ref}: {count}")
            for ex in examples:
                print(f"    [{ex['reason']}] {ex['msgid']}")
                print(f"      msgstr: {ex['msgstr']!r}")
                print(f"      refs:   {', '.join(ex['refs'])}")
            lang_failed += heuristic_failed

        if not checks:
            print("  Note: no exact critical profile configured; heuristic checks only.")

        if lang_failed == 0:
            print("  PASS")
        elif critical_failed and heuristic_failed:
            print(f"  FAIL: critical={critical_failed}, heuristic={heuristic_failed}")
        elif critical_failed:
            print(f"  FAIL: critical={critical_failed}")
        else:
            print(f"  FAIL: heuristic={heuristic_failed}")

        if lang_failed and lang in warning_only_langs:
            print("  Note: warning-only locale; issues reported but not counted as hard failure.")
        else:
            failed += lang_failed

    if failed:
        print(f"\nFAIL: {failed} quality issue(s) found.")
        return 1
    print("\nPASS: quality checks passed for critical strings and guarded-template heuristics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
