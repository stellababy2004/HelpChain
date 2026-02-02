#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n coverage checker: finds missing translations (empty msgstr) in .po files
and ranks by "visibility" score, using source references (#: templates/...)
Usage:
  python scripts/i18n_coverage.py --lang fr --top 30
  python scripts/i18n_coverage.py --lang bg --top 30
  python scripts/i18n_coverage.py --lang fr --only-templates
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from typing import List


VISIBLE_HINTS = [
    # UI text
    "title",
    "hero",
    "cta",
    "button",
    "nav",
    "navbar",
    "footer",
    "badge",
    "label",
    "search",
    "placeholder",
    # Pages we care about early
    "home",
    "base",
    "submit",
    "categories",
    "about",
    "volunteer",
    "request",
    "pilot",
    "privacy",
    "terms",
]

HIGH_VALUE_TEMPLATES = [
    "templates/base.html",
    "templates/home_new_slim.html",
    "templates/home_new.html",
    "templates/submit_request.html",
    "templates/volunteer_dashboard.html",
    "templates/volunteer_request_details.html",
    "templates/all_categories.html",
]


@dataclass
class PoEntry:
    msgid: str
    msgstr: str
    refs: List[str]  # lines like: templates/home_new_slim.html:14


def unescape_po(s: str) -> str:
    """Minimal unescape for \\", \\n and \\\\ in PO quoted strings."""
    return s.encode("utf-8").decode("unicode_escape")


def parse_po(path: str) -> List[PoEntry]:
    entries: List[PoEntry] = []
    refs: List[str] = []
    msgid_parts: List[str] = []
    msgstr_parts: List[str] = []
    state = None  # "msgid" | "msgstr" | None

    def flush():
        nonlocal refs, msgid_parts, msgstr_parts
        if msgid_parts:
            msgid = "".join(msgid_parts)
            msgstr = "".join(msgstr_parts)
            entries.append(PoEntry(msgid=msgid, msgstr=msgstr, refs=list(refs)))
        refs.clear()
        msgid_parts.clear()
        msgstr_parts.clear()

    re_ref = re.compile(r"^#:\s+(.*)$")
    re_msgid = re.compile(r'^msgid\s+"(.*)"\s*$')
    re_msgstr = re.compile(r'^msgstr\s+"(.*)"\s*$')
    re_q = re.compile(r'^"(.*)"\s*$')

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # New entry boundary (blank line)
            if not line.strip():
                flush()
                state = None
                continue

            mref = re_ref.match(line)
            if mref:
                refs.extend(mref.group(1).split())
                continue

            mid = re_msgid.match(line)
            if mid:
                state = "msgid"
                msgid_parts[:] = [unescape_po(mid.group(1))]
                msgstr_parts.clear()
                continue

            mstr = re_msgstr.match(line)
            if mstr:
                state = "msgstr"
                msgstr_parts[:] = [unescape_po(mstr.group(1))]
                continue

            mq = re_q.match(line)
            if mq and state in ("msgid", "msgstr"):
                if state == "msgid":
                    msgid_parts.append(unescape_po(mq.group(1)))
                else:
                    msgstr_parts.append(unescape_po(mq.group(1)))
                continue

            # Ignore other comment types (#, #., #, fuzzy, etc.)

    flush()
    # Drop the header entry (msgid == "")
    entries = [e for e in entries if e.msgid.strip() != ""]
    return entries


def visibility_score(entry: PoEntry, only_templates: bool) -> int:
    score = 0
    refs = entry.refs or []
    template_refs = [r for r in refs if r.startswith("templates/")]
    py_refs = [r for r in refs if r.endswith(".py") or "/src/" in r or "backend/" in r]

    if template_refs:
        score += 50 + 3 * len(template_refs)
    if py_refs and not template_refs:
        score += 10 + 1 * len(py_refs)

    if only_templates and not template_refs:
        return 0  # filtered out later

    for hv in HIGH_VALUE_TEMPLATES:
        if any(r.startswith(hv + ":") for r in template_refs):
            score += 25

    t = entry.msgid.strip()
    if len(t) <= 18:
        score += 18
    elif len(t) <= 40:
        score += 10
    else:
        score += 4

    low = t.lower()
    if any(k in low for k in ["submit", "search", "login", "sign", "help", "open", "cancel", "progress", "see all"]):
        score += 12

    ref_join = " ".join(refs).lower()
    if any(h in ref_join for h in VISIBLE_HINTS):
        score += 8

    if re.search(r"[{}<>]|%\\(.*?\\)s", t):
        score -= 8

    return max(score, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="fr", help="Language code (fr|bg|en)")
    ap.add_argument("--top", type=int, default=30, help="Top N missing translations")
    ap.add_argument("--only-templates", action="store_true", help="Only consider strings referenced from templates/")
    args = ap.parse_args()

    po_path = os.path.join("translations", args.lang, "LC_MESSAGES", "messages.po")
    if not os.path.exists(po_path):
        raise SystemExit(f"PO not found: {po_path}")

    entries = parse_po(po_path)

    missing = []
    for e in entries:
        if e.msgstr.strip() == "":
            sc = visibility_score(e, only_templates=args.only_templates)
            if sc > 0:
                missing.append((sc, e))

    missing.sort(key=lambda x: x[0], reverse=True)
    missing = missing[: args.top]

    print(f"\n=== i18n coverage: missing translations for '{args.lang}' ===")
    print(f"PO: {po_path}")
    print(f"Filter: {'templates only' if args.only_templates else 'all refs'}")
    print(f"Found missing: {len(missing)} (top {args.top})\n")

    for i, (sc, e) in enumerate(missing, start=1):
        refs = e.refs or []
        tpl = [r for r in refs if r.startswith("templates/")]
        other = [r for r in refs if not r.startswith("templates/")]
        show = (tpl[:3] + other[:3])[:3]

        msgid_preview = e.msgid.replace("\n", "\\n")
        if len(msgid_preview) > 110:
            msgid_preview = msgid_preview[:107] + "..."

        print(f"{i:02d}. score={sc}")
        print(f"    msgid: {msgid_preview}")
        if show:
            print(f"    refs:  {', '.join(show)}")
        else:
            print(f"    refs:  (none)")
        print()

    print("Tip: After filling msgstr values, run: pybabel compile -d translations\n")


if __name__ == "__main__":
    main()
