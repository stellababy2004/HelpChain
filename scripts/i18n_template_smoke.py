#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from babel.messages import pofile

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
        description="Smoke check i18n for guarded templates (optionally runs refresh pipeline first)."
    )
    p.add_argument("--langs", nargs="+", default=["bg"], help="Locales to refresh in pipeline step (default: bg)")
    p.add_argument("--gate-lang", default="bg", help="Locale used for missing-translation gate (default: bg)")
    p.add_argument("--source-locale", default="fr", help="Source locale for Argos pipeline pass (default: fr)")
    p.add_argument("--source-locales", nargs="*", default=[], help="Fallback chain for Argos pipeline, e.g. en fr")
    p.add_argument("--templates", nargs="*", default=None, help="Template paths to gate")
    p.add_argument("--template-profile", choices=["core", "extended"], default="core", help="Guarded template preset")
    p.add_argument("--skip-pipeline", action="store_true", help="Skip i18n_refresh_pipeline step")
    p.add_argument("--continue-on-error", action="store_true", help="Pass through to pipeline")
    p.add_argument("--overwrite-identical-only", action="store_true", help="Pass through to pipeline")
    p.add_argument("--max-messages", type=int, default=0, help="Pass through to pipeline")
    p.add_argument("--dry-run", action="store_true", help="Print pipeline command but do not execute it")
    p.add_argument("--show", type=int, default=30, help="Max missing entries to print")
    return p.parse_args()


def run(cmd: list[str], env: dict[str, str], dry_run: bool = False) -> int:
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"\n$ {printable}")
    if dry_run:
        return 0
    return subprocess.run(cmd, env=env).returncode


def load_catalog(po_path: Path, locale: str):
    with po_path.open("r", encoding="utf-8") as f:
        return pofile.read_po(f, locale=locale)


def is_empty_translation(msg) -> bool:
    s = msg.string
    if isinstance(s, str):
        return not s.strip()
    if isinstance(s, (tuple, list)):
        return not any((x or "").strip() for x in s)
    if isinstance(s, dict):
        return not any((x or "").strip() for x in s.values())
    return True


def format_msgid(msgid) -> str:
    if isinstance(msgid, (tuple, list)):
        text = str(msgid[0])
    else:
        text = str(msgid)
    text = text.replace("\n", "\\n")
    if len(text) > 140:
        text = text[:137] + "..."
    return text


def collect_missing_for_templates(po_path: Path, locale: str, templates: set[str]) -> list[dict]:
    catalog = load_catalog(po_path, locale)
    rows: list[dict] = []
    for msg in catalog:
        if not getattr(msg, "id", None):
            continue
        if getattr(msg, "obsolete", False):
            continue
        if not is_empty_translation(msg):
            continue
        locations = list(getattr(msg, "locations", []) or [])
        template_refs = []
        for loc in locations:
            if not isinstance(loc, tuple) or not loc:
                continue
            path = str(loc[0]).replace("\\", "/")
            line = loc[1] if len(loc) > 1 else "?"
            if path in templates:
                template_refs.append(f"{path}:{line}")
        if not template_refs:
            continue
        rows.append(
            {
                "msgid": format_msgid(msg.id),
                "refs": template_refs,
            }
        )
    rows.sort(key=lambda x: (x["refs"][0], x["msgid"]))
    return rows


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")

    py = str(Path(".venv") / "Scripts" / "python.exe")
    if not Path(py).exists():
        py = sys.executable

    selected_templates = args.templates or (EXTENDED_GUARDED_TEMPLATES if args.template_profile == "extended" else DEFAULT_GUARDED_TEMPLATES)
    templates = {t.replace("\\", "/") for t in selected_templates}
    po_path = Path("translations") / args.gate_lang / "LC_MESSAGES" / "messages.po"
    if not po_path.exists():
        print(f"PO file not found for gate locale '{args.gate_lang}': {po_path}", file=sys.stderr)
        return 2

    if not args.skip_pipeline:
        pipeline_cmd = [
            py,
            "scripts/i18n_refresh_pipeline.py",
            "--langs",
            *args.langs,
        ]
        if args.source_locales:
            pipeline_cmd += ["--source-locales", *args.source_locales]
        else:
            pipeline_cmd += ["--source-locale", args.source_locale]
        if args.continue_on_error:
            pipeline_cmd.append("--continue-on-error")
        if args.overwrite_identical_only:
            pipeline_cmd.append("--overwrite-identical-only")
        if args.max_messages:
            pipeline_cmd += ["--max-messages", str(args.max_messages)]
        code = run(pipeline_cmd, env=env, dry_run=args.dry_run)
        if code != 0:
            print(f"[FAIL] i18n_refresh_pipeline failed (exit={code})", file=sys.stderr)
            return code

    rows = collect_missing_for_templates(po_path, args.gate_lang, templates)
    print("\n=== i18n template smoke ===")
    print(f"gate_lang: {args.gate_lang}")
    print("guarded templates:")
    for t in sorted(templates):
        print(f"- {t}")

    if not rows:
        print("\nPASS: no missing translations found in guarded templates.")
        return 0

    by_file: dict[str, int] = {}
    for row in rows:
        for ref in row["refs"]:
            file_ref = ref.split(":", 1)[0]
            by_file[file_ref] = by_file.get(file_ref, 0) + 1

    print(f"\nFAIL: found {len(rows)} missing translation(s) in guarded templates.")
    print("\nBy template:")
    for file_ref, count in sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"- {file_ref}: {count}")
    print()
    for i, row in enumerate(rows[: args.show], start=1):
        print(f"{i:02d}. msgid: {row['msgid']}")
        print(f"    refs:  {', '.join(row['refs'])}")
    if len(rows) > args.show:
        print(f"\n... and {len(rows) - args.show} more")
    print("\nTip: run the refresh pipeline, fill remaining msgstr values, then compile translations.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
