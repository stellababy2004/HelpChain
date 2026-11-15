#!/usr/bin/env python3
"""Read-only GitHub PR/CI digest. No external writes, secrets or PII in output."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "stellababy2004/HelpChain")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com/repos/" + REPO
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "helpchain-readonly-digest"}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN


def get(path):
    request = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    try:
        prs = get("/pulls?state=open&per_page=100")
        runs = get("/actions/runs?per_page=100")["workflow_runs"]
    except (urllib.error.URLError, ValueError, KeyError) as exc:
        print("GitHub API read failed: " + type(exc).__name__, file=sys.stderr)
        return 1

    lines = [
        "# HelpChain — GitHub read-only digest",
        "",
        "Generated UTC: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "Repository: " + REPO,
        "",
        "## Open PRs (first 100; truncated if more)",
    ]
    for pr in prs:
        lines.append(
            "- #" + str(pr["number"]) + " " + pr["title"].replace("\n", " ")[:120]
            + " | " + ("DRAFT" if pr["draft"] else "OPEN")
            + " | head " + pr["head"]["sha"][:12]
            + " | " + pr["html_url"]
        )
    if not prs:
        lines.append("- None")
    lines += ["", "## Failed or incomplete recent workflow runs (first 100)"]
    problematic = [
        r for r in runs
        if r["status"] != "completed" or r["conclusion"] not in ("success", "skipped", "neutral")
    ]
    for run in problematic:
        lines.append(
            "- " + run["name"][:90] + " | " + run["status"]
            + "/" + str(run["conclusion"]) + " | SHA "
            + (run.get("head_sha") or "unknown")[:12]
            + " | " + run["html_url"]
        )
    if not problematic:
        lines.append("- None in fetched window (not proof of all checks PASS)")
    lines += [
        "", "## Interpretation",
        "- This report does NOT establish PR mergeability, required checks, scan evidence, or production deployment.",
        "- No auto-merge, deploy, risk acceptance, Notion edits, or outbound messages.",
        "- Verify head SHA, required checks, trusted verdict and scan provenance before merge.",
        "- API pagination is capped at 100 PRs and 100 runs; treat completeness as unverified.",
    ]
    output = "\n".join(lines) + "\n"
    os.makedirs("reports", exist_ok=True)
    with open("reports/github-digest.md", "w", encoding="utf-8") as handle:
        handle.write(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
