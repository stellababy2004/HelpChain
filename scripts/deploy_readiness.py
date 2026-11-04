"""Verify that the current commit has a successful FULL GitHub Quality Gate.

This is a read-only release check. It never deploys, changes GitHub state, or
accepts FAST/local results as evidence. Authentication is delegated to the
already configured GitHub CLI credential store; no token is read or written by
this script.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = "quality-gate-full.yml"


def blocked(message: str) -> int:
    print(f"BLOCKED: {message}")
    return 2


def gh_json(args: list[str]) -> object:
    try:
        result = subprocess.run(["gh", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"GitHub CLI unavailable: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"gh exited with {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub CLI returned invalid JSON") from exc


def get_repo() -> str:
    remote = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$", remote)
    if not match:
        raise RuntimeError("origin is not a GitHub repository")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", default="", help="Commit SHA; defaults to HEAD")
    parser.add_argument("--repo", default="", help="owner/repository; defaults to origin")
    args = parser.parse_args()
    sha = args.sha or subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    repo = args.repo or get_repo()
    print(f"Checking FULL Quality Gate for {repo}@{sha}")
    try:
        payload = gh_json([
            "api", f"repos/{repo}/actions/workflows/{WORKFLOW}/runs",
            "-f", f"head_sha={sha}", "-f", "per_page=20",
        ])
    except RuntimeError as exc:
        return blocked(str(exc))
    runs = [run for run in payload.get("workflow_runs", []) if run.get("head_sha") == sha]
    successful = [run for run in runs if run.get("status") == "completed" and run.get("conclusion") == "success"]
    if successful:
        run = sorted(successful, key=lambda item: item.get("updated_at", ""), reverse=True)[0]
        print(f"PASS: FULL Quality Gate run {run.get('id')} completed successfully")
        print(f"URL: {run.get('html_url', '')}")
        return 0
    if runs:
        states = ", ".join(f"{run.get('status')}/{run.get('conclusion')}" for run in runs[:5])
        return blocked(f"no successful completed FULL run for this SHA ({states})")
    return blocked("no GitHub Actions Quality Gate run exists for this SHA")


if __name__ == "__main__":
    raise SystemExit(main())
