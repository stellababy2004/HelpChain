#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path("docs/institutions/generated")
OUT = Path("docs/institutions/pdfs")


def main() -> int:
    if not SRC.exists():
        print(f"[ERROR] Source directory missing: {SRC}", file=sys.stderr)
        return 2

    if shutil.which("pandoc") is None:
        print("[ERROR] pandoc not found in PATH", file=sys.stderr)
        return 2
    if shutil.which("wkhtmltopdf") is None:
        print("[ERROR] wkhtmltopdf not found in PATH", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)

    md_files = sorted(SRC.glob("HelpChain_Overview_*.md"))
    if not md_files:
        print(f"[ERROR] No markdown files found in {SRC}", file=sys.stderr)
        return 2

    for md in md_files:
        pdf = OUT / md.with_suffix(".pdf").name
        cmd = [
            "pandoc",
            str(md),
            "-o",
            str(pdf),
            "--pdf-engine=wkhtmltopdf",
            "--metadata",
            "title=HelpChain Institutional Overview",
        ]
        print(f"[PDF] {pdf.name}")
        subprocess.run(cmd, check=True)

    print(f"[DONE] PDFs generated in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

