#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


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
        description="Stable i18n refresh pipeline: extract -> update -> Argos translate -> placeholder fix/check -> compile."
    )
    p.add_argument("--langs", nargs="+", required=True, help="Locales to refresh (e.g. bg es de en fr)")
    p.add_argument("--source-locale", default="fr", help="Source locale for Argos translation pass (deprecated if --source-locales is used)")
    p.add_argument(
        "--source-locales",
        nargs="*",
        default=[],
        help="Fallback chain for Argos source locales, e.g. en fr (runs multiple passes).",
    )
    p.add_argument("--skip-extract", action="store_true", help="Skip pybabel extract step")
    p.add_argument("--skip-translate", action="store_true", help="Skip Argos translation step")
    p.add_argument("--skip-compile", action="store_true", help="Skip pybabel compile step")
    p.add_argument(
        "--overwrite-identical-only",
        action="store_true",
        help="Argos cleanup mode: overwrite only msgstr == msgid (safe second pass).",
    )
    p.add_argument("--max-messages", type=int, default=0, help="Limit translated messages per locale in Argos step")
    p.add_argument("--no-placeholder-fix", action="store_true", help="Skip automatic placeholder artifact fixer")
    p.add_argument("--no-placeholder-check", action="store_true", help="Skip placeholder mismatch checker")
    p.add_argument("--dry-run", action="store_true", help="Print commands but do not execute them")
    p.add_argument("--continue-on-error", action="store_true", help="Continue remaining steps/locales on command errors")
    p.add_argument("--skip-native-autofill", action="store_true", help="Skip native-source autofill step (e.g. Cyrillic msgid -> bg)")
    return p.parse_args()


def run(cmd: list[str], *, env: dict[str, str] | None = None, dry_run: bool = False) -> int:
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"\n$ {printable}")
    if dry_run:
        return 0
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def fail_or_continue(code: int, what: str, *, continue_on_error: bool) -> None:
    if code == 0:
        return
    msg = f"[FAIL] {what} (exit={code})"
    if continue_on_error:
        print(msg)
        return
    raise SystemExit(msg)


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()

    root = Path(".")
    py = str(Path(".venv") / "Scripts" / "python.exe")
    pybabel = str(Path(".venv") / "Scripts" / "pybabel.exe")
    if not Path(py).exists():
        py = sys.executable
    if not Path(pybabel).exists():
        pybabel = "pybabel"

    langs = [l.strip() for l in args.langs if l.strip()]
    if not langs:
        raise SystemExit("No languages specified.")

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    # Optional local cache path for tools that write under user profile on Windows (e.g. Argos/Stanza)
    local_data = root / ".cache" / "local-share"
    try:
        local_data.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    env.setdefault("XDG_DATA_HOME", str(local_data.resolve()))

    print("=== i18n refresh pipeline ===")
    print(f"langs={langs}")
    source_locales = [s.strip() for s in (args.source_locales or []) if s.strip()]
    if not source_locales:
        source_locales = [args.source_locale]
    print(f"source_locales={source_locales}")
    print(f"XDG_DATA_HOME={env.get('XDG_DATA_HOME')}")

    if not args.skip_extract:
        code = run([pybabel, "extract", "-F", "babel.cfg", "-o", "messages.pot", "."], env=env, dry_run=args.dry_run)
        fail_or_continue(code, "pybabel extract", continue_on_error=args.continue_on_error)

    code = run(
        [py, "scripts/i18n_update_catalogs.py", "--pot", "messages.pot", "--translations-dir", "translations", "--langs", *langs],
        env=env,
        dry_run=args.dry_run,
    )
    fail_or_continue(code, "catalog update", continue_on_error=args.continue_on_error)

    if not args.skip_native_autofill:
        code = run([py, "scripts/i18n_autofill_native.py", "--langs", *langs], env=env, dry_run=args.dry_run)
        fail_or_continue(code, "native autofill", continue_on_error=args.continue_on_error)

    if not args.skip_translate:
        for src_locale in source_locales:
            argos_cmd = [py, "scripts/argos_translate_po.py", "--source-locale", src_locale, "--targets", *langs]
            if args.overwrite_identical_only:
                argos_cmd.append("--overwrite-identical-only")
            if args.max_messages:
                argos_cmd += ["--max-messages", str(args.max_messages)]
            code = run(argos_cmd, env=env, dry_run=args.dry_run)
            fail_or_continue(code, f"Argos translate ({src_locale})", continue_on_error=args.continue_on_error)

    if not args.no_placeholder_fix:
        code = run([py, "scripts/i18n_placeholder_fix.py", "--langs", *langs], env=env, dry_run=args.dry_run)
        fail_or_continue(code, "placeholder fix", continue_on_error=args.continue_on_error)

    if not args.no_placeholder_check:
        code = run([py, "scripts/i18n_placeholder_check.py", "--langs", *langs, "--show", "20", "--per-lang", "10"], env=env, dry_run=args.dry_run)
        fail_or_continue(code, "placeholder check", continue_on_error=args.continue_on_error)

    if not args.skip_compile:
        for lang in langs:
            code = run([pybabel, "compile", "-f", "-d", "translations", "-l", lang], env=env, dry_run=args.dry_run)
            fail_or_continue(code, f"compile {lang}", continue_on_error=args.continue_on_error)

    print("\nDone. Restart server + Ctrl+F5 to see template/i18n changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
