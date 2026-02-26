#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CODE_RE = re.compile(r"'code'\s*:\s*'([^']+)'")


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract locale codes from accessibility language menu in templates/base.html")
    p.add_argument("--template", default="templates/base.html", help="Template file containing hc_languages list")
    p.add_argument("--format", choices=["space", "csv", "lines"], default="space", help="Output format")
    return p.parse_args()


def main() -> int:
    _configure_stdio_utf8()
    args = parse_args()
    path = Path(args.template)
    if not path.exists():
        print(f"Template not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")
    codes = []
    seen = set()
    for m in CODE_RE.finditer(text):
        code = m.group(1).strip()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    if not codes:
        print("No locale codes found.", file=sys.stderr)
        return 1
    if args.format == "csv":
        print(",".join(codes))
    elif args.format == "lines":
        print("\n".join(codes))
    else:
        print(" ".join(codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

