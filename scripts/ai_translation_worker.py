#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Periodic worker for AI translation suggestions. "
            "Generates suggestion packs only (no DB writes)."
        )
    )
    p.add_argument("--target-locales", default="en,de,bg")
    p.add_argument("--source", choices=("registry", "db", "auto"), default="auto")
    p.add_argument("--source-locale", default="fr")
    p.add_argument("--view", choices=("ops", "core", "inventory", "all"), default="ops")
    p.add_argument("--provider", choices=("hf_local", "rules"), default="hf_local")
    p.add_argument("--limit", type=int, default=300)
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--interval-seconds", type=int, default=600)
    p.add_argument("--runs", type=int, default=1, help="How many cycles to execute. 1 = one-shot.")
    p.add_argument(
        "--out-dir",
        default="reports/translation_tasks",
        help="Directory for generated suggestion packs.",
    )
    p.add_argument(
        "--latest-file",
        default="reports/translation_tasks/latest.json",
        help="Path to mirror latest pack summary/pointer.",
    )
    p.add_argument(
        "--include-existing",
        action="store_true",
        help="Also generate suggestions for keys that already have DB override.",
    )
    return p.parse_args()


def _run_batch(args: argparse.Namespace, out_file: Path) -> int:
    py = str(Path(".venv") / "Scripts" / "python.exe")
    if not Path(py).exists():
        py = sys.executable

    cmd = [
        py,
        "scripts/ai_batch_translate.py",
        "--target-locales",
        args.target_locales,
        "--source",
        args.source,
        "--source-locale",
        args.source_locale,
        "--view",
        args.view,
        "--provider",
        args.provider,
        "--limit",
        str(max(1, args.limit)),
        "--batch-size",
        str(max(1, args.batch_size)),
        "--output",
        str(out_file),
    ]
    if args.include_existing:
        cmd.append("--include-existing")

    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd)
    return int(proc.returncode)


def _write_latest_pointer(*, latest_file: Path, out_file: Path) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "latest_pack": str(out_file).replace("\\", "/"),
    }
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    latest_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    _configure_stdio_utf8()
    args = _parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_file = Path(args.latest_file)

    runs = max(1, args.runs)
    for i in range(1, runs + 1):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_file = out_dir / f"ai_tasks_{stamp}.json"
        print(f"[worker] run {i}/{runs} -> {out_file}")

        rc = _run_batch(args, out_file)
        if rc != 0:
            print(f"[worker] run failed (exit={rc})", file=sys.stderr)
        else:
            _write_latest_pointer(latest_file=latest_file, out_file=out_file)
            print("[worker] run completed.")

        if i < runs:
            sleep_sec = max(1, args.interval_seconds)
            print(f"[worker] sleeping {sleep_sec}s...")
            time.sleep(sleep_sec)

    print("[worker] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
