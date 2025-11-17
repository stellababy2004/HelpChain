"""Run local security audit using pip-audit and safety.
Outputs:
 - pip_audit_results.txt (table)
 - safety_results.json (raw JSON)
Usage:
  python scripts/run_security_audit.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(__file__))

PIP_AUDIT_CMD = [sys.executable, "-m", "pip_audit", "--progress-spinner", "off"]
# Prefer new `scan` command; fallback to deprecated `check`.
SAFETY_SCAN_CMD = [sys.executable, "-m", "safety", "scan", "--json"]
SAFETY_CHECK_CMD = [sys.executable, "-m", "safety", "check", "--json"]


def ensure_tools():
    need = []
    for mod, pkg in [("pip_audit", "pip-audit"), ("safety", "safety")]:
        try:
            __import__(mod)
        except ImportError:
            need.append(pkg)
    if need:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *need])


def run_pip_audit():
    try:
        res = subprocess.run(PIP_AUDIT_CMD, capture_output=True, text=True)
        with open("pip_audit_results.txt", "w", encoding="utf-8") as f:
            f.write(res.stdout or "")
        print("[pip-audit] Completed; results saved to pip_audit_results.txt")
        return res.stdout
    except Exception as e:
        print("[pip-audit] Failed:", e)
        return ""


def _extract_json_block(raw: str) -> str:
    """Extract the first valid JSON object from noisy stdout (deprecated banners)."""
    if not raw:
        return "{}"
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return "{}"
    return raw[start : end + 1]


def _parse_safety(raw: str) -> dict:
    cleaned = _extract_json_block(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def run_safety(mode: str, timeout: int) -> list:
    if mode not in {"auto", "scan", "check"}:
        print(f"[safety] Invalid mode '{mode}', defaulting to auto")
        mode = "auto"
    if os.getenv("SAFETY_SKIP") == "1":
        print("[safety] Skipped via SAFETY_SKIP=1")
        return []
    poll_interval = 0.5

    # Determine command order based on mode
    if mode == "scan":
        candidates = [(SAFETY_SCAN_CMD, "scan")]
    elif mode == "check":
        candidates = [(SAFETY_CHECK_CMD, "check")]
    else:  # auto
        candidates = [(SAFETY_SCAN_CMD, "scan"), (SAFETY_CHECK_CMD, "check")]

    for cmd, label in candidates:
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            elapsed = 0.0
            while proc.poll() is None and elapsed < timeout:
                elapsed += poll_interval
                time.sleep(poll_interval)
            if proc.poll() is None:
                proc.kill()
                print(
                    f"[safety] {label} timed out after {timeout}s; killing and fallback..."
                )
                continue
            stdout, stderr = proc.communicate()
            raw = stdout or ""
            with open("safety_results.json", "w", encoding="utf-8") as f:
                f.write(raw)
            data = _parse_safety(raw)
            if not data and proc.returncode != 0:
                print(
                    f"[safety] {label} returned non-zero and no JSON; stderr: {stderr[:120]}"
                )
                continue
            vulns = []
            if isinstance(data, dict):
                if "issues" in data and isinstance(data.get("issues"), list):
                    vulns = data["issues"]
                elif "vulnerabilities" in data and isinstance(
                    data.get("vulnerabilities"), list
                ):
                    vulns = data["vulnerabilities"]
            print(
                f"[safety] {len(vulns)} findings via {label}; saved to safety_results.json"
            )
            return vulns
        except Exception as e:
            print(f"[safety] {label} failed: {e}")
            continue
    print("[safety] Completely failed; returning empty list")
    return []


def summarize(pip_audit_out: str, safety_vulns: list):
    print("\n=== SUMMARY ===")
    # Simple counts
    pa_count = 0
    for line in pip_audit_out.splitlines():
        if line.strip() and "|" in line and not line.lower().startswith("package"):
            pa_count += 1
    print(f"pip-audit potential findings (table rows excluding header): {pa_count}")
    print(f"safety vulnerabilities: {len(safety_vulns)}")
    if safety_vulns:
        # Show first few CVEs / IDs
        for v in safety_vulns[:5]:
            print(
                " -", v.get("package_name"), v.get("severity"), v.get("advisory")[:80]
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run dependency vulnerability audit (pip-audit + safety)."
    )
    parser.add_argument(
        "--no-safety", action="store_true", help="Skip safety scan even if available."
    )
    parser.add_argument(
        "--safety-timeout",
        type=int,
        default=30,
        help="Timeout in seconds for safety command.",
    )
    parser.add_argument(
        "--safety-mode",
        choices=["auto", "scan", "check"],
        default="auto",
        help="Force safety command variant or auto fallback.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ensure_tools()
    pa_out = run_pip_audit()
    if args.no_safety:
        print("[safety] Skipped via --no-safety flag")
        safety_vulns = []
    else:
        safety_vulns = run_safety(mode=args.safety_mode, timeout=args.safety_timeout)
    summarize(pa_out, safety_vulns)
    print("Done.")
