#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import polib


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")
I18N_CALL_RE = re.compile(r"""\b_\s*\(\s*(?P<q>["'])(?P<msgid>[^"']+)(?P=q)(?=\s*[,)])""")
JINJA_RE = re.compile(r"{{.*?}}|{%.*?%}|{#.*?#}", re.DOTALL)
PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)


@dataclass(frozen=True)
class AddedLine:
    file: str
    line_no: int
    text: str


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="CI i18n guard for new untranslated keys and new hardcoded template text.")
    ap.add_argument("--base-ref", default="origin/main", help="Git base ref for diff (default: origin/main).")
    ap.add_argument("--fr-po", default="translations/fr/LC_MESSAGES/messages.po")
    ap.add_argument("--show", type=int, default=80, help="Max violations to print per section.")
    return ap.parse_args()


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def resolve_base_ref(preferred: str) -> str:
    ok = _run_git(["rev-parse", "--verify", preferred]).returncode == 0
    if ok:
        return preferred
    if _run_git(["rev-parse", "--verify", "HEAD~1"]).returncode == 0:
        return "HEAD~1"
    return "HEAD"


def changed_files(base_ref: str) -> list[str]:
    cp = _run_git(["diff", "--name-only", base_ref])
    if cp.returncode != 0:
        return []
    out = []
    for line in cp.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if path:
            out.append(path)
    return out


def _is_archived_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return normalized.startswith("_archive/")


def added_lines_for_file(base_ref: str, file_path: str) -> list[AddedLine]:
    if _is_archived_path(file_path):
        return []

    cp = _run_git(["diff", "--unified=0", "--no-color", base_ref, "--", file_path])
    if cp.returncode != 0:
        return []

    out: list[AddedLine] = []
    cur_new_line = 0
    for raw in cp.stdout.splitlines():
        h = HUNK_RE.match(raw)
        if h:
            cur_new_line = int(h.group("start"))
            continue
        if raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        if raw.startswith("+"):
            out.append(AddedLine(file=file_path, line_no=cur_new_line, text=raw[1:]))
            cur_new_line += 1
            continue
        if raw.startswith(" "):
            cur_new_line += 1
            continue
        # Removed lines ('-') do not advance new-file pointer.
    return out


def load_fr_translated_msgids(po_path: Path) -> set[str]:
    if not po_path.exists():
        return set()
    po = polib.pofile(str(po_path))
    translated: set[str] = set()
    for e in po:
        if e.obsolete or not e.msgid:
            continue
        if str(e.msgstr or "").strip():
            translated.add(str(e.msgid))
    return translated


def _is_visible_chunk(s: str) -> bool:
    txt = " ".join(s.split()).strip()
    if len(txt) < 2:
        return False
    if PUNCT_ONLY_RE.fullmatch(txt):
        return False
    # Pure numeric markers such as 01, 02, 03 are not translatable copy.
    if re.fullmatch(r"\d+(?:[.,]\d+)?", txt):
        return False
    return True


def _mask_jinja(source: str) -> str:
    """Hide template syntax/translated blocks without changing HTML positions."""
    def blank(text: str) -> str:
        return re.sub(r"[^\n]", " ", text)

    parts: list[str] = []
    cursor = 0
    in_trans_block = False
    for match in JINJA_RE.finditer(source):
        preceding = source[cursor:match.start()]
        parts.append(blank(preceding) if in_trans_block else preceding)
        token = match.group()
        parts.append(blank(token))
        if re.match(r"{%[-+]?\s*trans\b", token):
            in_trans_block = True
        elif re.match(r"{%[-+]?\s*endtrans\b", token):
            in_trans_block = False
        cursor = match.end()
    tail = source[cursor:]
    parts.append(blank(tail) if in_trans_block else tail)
    return "".join(parts)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.hidden_tag: str | None = None
        self.chunks: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script"}:
            self.hidden_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self.hidden_tag:
            self.hidden_tag = None

    def handle_data(self, data: str) -> None:
        if self.hidden_tag:
            return
        start_line, _ = self.getpos()
        for offset, text in enumerate(data.splitlines()):
            self.chunks.append((start_line + offset, " ".join(text.split()).strip()))


REPORT_OPERATIONS_ALLOWED_LABELS = {
    "Sant? op?rationnelle",
    "/100",
    "D?cision recommand?e",
    "Perimetre",
    "Fenetre",
    "jours",
    "Generation",
    "Stabilite",
    "Annexe",
    "Definition des indicateurs",
}


def _is_allowed_report_operations_label(file_path: str, txt: str) -> bool:
    return (
        file_path.replace("\\", "/").endswith("templates/admin/reports_operations.html")
        and txt in REPORT_OPERATIONS_ALLOWED_LABELS
    )


def detect_hardcoded_in_template_lines(lines: list[AddedLine], source: str) -> list[tuple[str, int, str]]:
    # Parse the complete file: opening tags/trans blocks may be outside diff hunks.
    parser = _VisibleTextParser()
    parser.feed(_mask_jinja(source))
    parser.close()
    added = {row.line_no: row for row in lines}
    offenders: list[tuple[str, int, str]] = []
    for line_no, txt in parser.chunks:
        row = added.get(line_no)
        if row is None:
            continue
        if _is_visible_chunk(txt) and not _is_allowed_report_operations_label(row.file, txt):
            offenders.append((row.file, row.line_no, txt))

    # de-duplicate stable order
    seen: set[tuple[str, int, str]] = set()
    uniq: list[tuple[str, int, str]] = []
    for item in offenders:
        if item in seen:
            continue
        seen.add(item)
        uniq.append(item)
    return uniq


def main() -> int:
    args = parse_args()
    base_ref = resolve_base_ref(args.base_ref)
    # Include staged and unstaged fixes locally, retaining the PR merge base.
    merge_base = _run_git(["merge-base", base_ref, "HEAD"])
    if merge_base.returncode != 0:
        print(f"ERROR: Cannot resolve merge base for {base_ref}.", file=sys.stderr)
        return 1
    diff_base = merge_base.stdout.strip()
    files = changed_files(diff_base)

    added_by_file: dict[str, list[AddedLine]] = {}
    for fp in files:
        rows = added_lines_for_file(diff_base, fp)
        if rows:
            added_by_file[fp] = rows

    # Rule 1: new _("...") keys must have FR msgstr
    fr_translated = load_fr_translated_msgids(Path(args.fr_po))
    new_msgid_occurrences: dict[str, list[tuple[str, int]]] = {}

    for fp, rows in added_by_file.items():
        for row in rows:
            for m in I18N_CALL_RE.finditer(row.text):
                msgid = (m.group("msgid") or "").strip()
                if not msgid:
                    continue
                new_msgid_occurrences.setdefault(msgid, []).append((fp, row.line_no))

    missing_fr: list[tuple[str, list[tuple[str, int]]]] = []
    for msgid, refs in sorted(new_msgid_occurrences.items(), key=lambda x: x[0]):
        if msgid not in fr_translated:
            missing_fr.append((msgid, refs))

    # Rule 2: new hardcoded visible text in templates (not wrapped)
    hardcoded: list[tuple[str, int, str]] = []
    for fp, rows in added_by_file.items():
        if not fp.startswith("templates/"):
            continue
        if not any(fp.endswith(ext) for ext in (".html", ".jinja", ".jinja2")):
            continue
        source = Path(fp).read_text(encoding="utf-8")
        hardcoded.extend(detect_hardcoded_in_template_lines(rows, source))

    failed = False
    print("i18n CI guard")
    print(f"base_ref: {base_ref}")

    if missing_fr:
        failed = True
        print(f"\nERROR: New _() keys missing FR msgstr ({len(missing_fr)})")
        for msgid, refs in missing_fr[: args.show]:
            where = ", ".join(f"{f}:{ln}" for f, ln in refs[:4])
            if len(refs) > 4:
                where += f", +{len(refs) - 4} more"
            print(f"- {msgid} [{where}]")
        if len(missing_fr) > args.show:
            print(f"... +{len(missing_fr) - args.show} more")
    else:
        print("\nOK: No new _() keys without FR msgstr.")

    if hardcoded:
        failed = True
        print(f"\nERROR: New hardcoded visible template text ({len(hardcoded)})")
        for fp, ln, txt in hardcoded[: args.show]:
            print(f"- {fp}:{ln} -> {txt}")
        if len(hardcoded) > args.show:
            print(f"... +{len(hardcoded) - args.show} more")
    else:
        print("\nOK: No new hardcoded visible text in templates.")

    if failed:
        print("\nFAIL: i18n guard failed.")
        return 1
    print("\nPASS: i18n guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
