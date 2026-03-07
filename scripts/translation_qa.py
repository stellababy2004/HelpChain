#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import polib


RE_PRINTF_NAMED = re.compile(r"%\([A-Za-z0-9_]+\)[#0\- +]?(?:\d+)?(?:\.\d+)?[diouxXeEfFgGcrs]")
RE_PRINTF = re.compile(r"%(?:\d+\$)?[#0\- +]?(?:\d+)?(?:\.\d+)?[diouxXeEfFgGcrs]")
RE_BRACES = re.compile(r"\{[A-Za-z0-9_.-]+\}")
RE_JINJA = re.compile(r"(\{\{.*?\}\}|\{%.+?%\})", re.DOTALL)


@dataclass
class QaStats:
    lang: str
    missing: int = 0
    placeholder_errors: int = 0
    untranslated: int = 0
    suspicious_short: int = 0
    total: int = 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Translation QA scanner for gettext catalogs.")
    ap.add_argument("--translations-dir", default="translations")
    ap.add_argument("--domain", default="messages")
    ap.add_argument("--langs", nargs="*", default=[], help="Optional languages (e.g. en bg de).")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero when errors are found.")
    ap.add_argument("--short-ratio", type=float, default=0.30, help="Warn if len(msgstr) < ratio * len(msgid).")
    ap.add_argument("--json-out", default="", help="Optional JSON report output path.")
    ap.add_argument("--md-out", default="", help="Optional Markdown report output path.")
    ap.add_argument("--show", type=int, default=10, help="Examples per language per category.")
    return ap.parse_args()


def iter_po_files(root: Path, domain: str, langs: Iterable[str]) -> list[tuple[str, Path]]:
    if langs:
        out = []
        for lang in langs:
            po = root / lang / "LC_MESSAGES" / f"{domain}.po"
            if po.exists():
                out.append((lang, po))
        return out
    out = []
    for lang_dir in sorted(root.iterdir()):
        if not lang_dir.is_dir():
            continue
        po = lang_dir / "LC_MESSAGES" / f"{domain}.po"
        if po.exists():
            out.append((lang_dir.name, po))
    return out


def extract_placeholders(text: str) -> list[str]:
    placeholders = []
    for rx in (RE_JINJA, RE_PRINTF_NAMED, RE_PRINTF, RE_BRACES):
        placeholders.extend(rx.findall(text or ""))
    return placeholders


def normalize(s: str) -> str:
    return " ".join((s or "").split()).strip()


def scan_po(po_path: Path, lang: str, short_ratio: float) -> tuple[QaStats, dict]:
    po = polib.pofile(str(po_path))
    stats = QaStats(lang=lang)
    examples = {
        "missing": [],
        "placeholder": [],
        "untranslated": [],
        "short": [],
    }

    for e in po:
        if e.obsolete or not e.msgid:
            continue

        # Skip plural header-like and technical-only keys from short/untranslated heuristics
        msgid = str(e.msgid)
        msgstr = str(e.msgstr or "")
        stats.total += 1

        if not msgstr.strip():
            stats.missing += 1
            examples["missing"].append(msgid)
            continue

        src_ph = sorted(extract_placeholders(msgid))
        dst_ph = sorted(extract_placeholders(msgstr))
        if src_ph != dst_ph:
            stats.placeholder_errors += 1
            examples["placeholder"].append(msgid)

        if normalize(msgid) == normalize(msgstr) and len(msgid.strip()) > 3:
            stats.untranslated += 1
            examples["untranslated"].append(msgid)

        if len(msgid.strip()) > 6 and len(msgstr.strip()) < int(len(msgid.strip()) * short_ratio):
            stats.suspicious_short += 1
            examples["short"].append(msgid)

    return stats, examples


def write_reports(json_out: str, md_out: str, rows: list[dict], summary: list[QaStats]) -> None:
    if json_out:
        Path(json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(json_out).write_text(
            json.dumps(
                {
                    "summary": [asdict(s) for s in summary],
                    "details": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if md_out:
        Path(md_out).parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Translation QA Report",
            "",
            "Language | Total | Missing | Placeholder | Untranslated | Suspicious Short",
            "---|---:|---:|---:|---:|---:",
        ]
        for s in summary:
            lines.append(
                f"{s.lang} | {s.total} | {s.missing} | {s.placeholder_errors} | {s.untranslated} | {s.suspicious_short}"
            )
        Path(md_out).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.translations_dir)
    files = iter_po_files(root, args.domain, args.langs)
    if not files:
        print(f"No PO files found in {root}")
        return 2

    summary: list[QaStats] = []
    rows = []
    total_errors = 0

    for lang, po_file in files:
        stats, examples = scan_po(po_file, lang, args.short_ratio)
        summary.append(stats)
        rows.append({"lang": lang, "file": str(po_file), "examples": examples})
        lang_errors = stats.missing + stats.placeholder_errors
        total_errors += lang_errors

        print(f"\nChecking: {po_file}")
        print(
            f"  total={stats.total} missing={stats.missing} placeholder={stats.placeholder_errors} "
            f"untranslated={stats.untranslated} short={stats.suspicious_short}"
        )
        for key in ("missing", "placeholder", "untranslated", "short"):
            items = examples[key][: args.show]
            for msgid in items:
                label = "ERROR" if key in ("missing", "placeholder") else "WARN"
                print(f"  {label} [{key}] {msgid}")

    write_reports(args.json_out, args.md_out, rows, summary)

    if args.strict and total_errors > 0:
        print(f"\nFAIL: translation QA found {total_errors} error(s).")
        return 1
    print("\nPASS: translation QA completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

