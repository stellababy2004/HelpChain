"""Monitor whether upgrading to h11>=0.16.0 becomes feasible.

Strategy:
1. Fetch latest versions of httpx and httpcore from PyPI.
2. Create a temporary virtual environment.
3. Attempt installing: httpx==<latest> h11==0.16.0 . (httpcore will be pulled transitively.)
   - If installation succeeds (and h11==0.16.0 is present), the constraint has been relaxed.
4. If upgrade feasible and no existing open issue tracking it, auto-create a GitHub issue.

Exit codes:
 0 → Upgrade still blocked.
 1 → Upgrade feasible and issue created (or already exists).
 2 → Non-critical script error.

The script intentionally avoids external deps (uses stdlib only) so it can run in a clean runner.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Optional

PYPI_JSON = "https://pypi.org/pypi/{package}/json"


@dataclass
class PackageInfo:
    name: str
    latest: str


def fetch_latest(package: str) -> PackageInfo:
    url = PYPI_JSON.format(package=package)
    with urllib.request.urlopen(url, timeout=15) as resp:  # nosec B310
        data = json.load(resp)
    return PackageInfo(name=package, latest=data["info"]["version"])


def make_temp_venv(tmp: str) -> str:
    venv_dir = os.path.join(tmp, "venv")
    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def attempt_install(python_exe: str, httpx_version: str) -> bool:
    # Upgrade pip to improve resolver reliability.
    subprocess.run(
        [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    # Attempt installing desired combo; httpcore will be pulled automatically
    proc = subprocess.run(
        [python_exe, "-m", "pip", "install", f"httpx=={httpx_version}", "h11==0.16.0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        print("[monitor] Install failed (blocked)\n" + proc.stdout)
        return False
    # Verify installed h11 version.
    check = subprocess.run(
        [
            python_exe,
            "-c",
            "import h11, json; print(json.dumps({'h11': h11.__version__}))",
        ],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        print("[monitor] h11 import failed", check.stderr)
        return False
    version = json.loads(check.stdout)["h11"]
    success = version == "0.16.0"
    print(f"[monitor] Installed h11 version: {version} (success={success})")
    return success


def github_request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        req.data = data
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
        return json.load(resp)


def find_existing_issue(repo: str, token: str) -> bool:
    # Search open issues with a specific label in title substring.
    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100"
    issues = github_request("GET", url, token)
    for issue in issues:
        title = issue.get("title", "")
        if "deps: enable h11" in title.lower():
            print(f"[monitor] Existing issue found: #{issue['number']}")
            return True
    return False


def create_issue(repo: str, token: str, httpx_version: str) -> None:
    body = (
        f"Upgrade feasibility detected: able to install httpx=={httpx_version} + h11==0.16.0 without resolver conflicts.\n\n"
        "Action items:\n"
        f"1. Pin httpx to {httpx_version} and add h11>=0.16.0 in requirements.in.\n"
        "2. Re-run security audit to confirm advisory GHSA-vqfr-h8mv-ghfj resolved.\n"
        "3. Remove BLOCKED note from SECURITY_TASKS.md.\n"
        "Automated detection script: scripts/monitor_http_stack_upgrade.py"
    )
    payload = {
        "title": f"deps: enable h11>=0.16.0 (httpx {httpx_version} compatible)",
        "body": body,
        "labels": ["security", "dependencies"],
    }
    url = f"https://api.github.com/repos/{repo}/issues"
    issue = github_request("POST", url, token, payload)
    print(f"[monitor] Created issue #{issue['number']}")


def main() -> int:
    print("[monitor] Starting http stack upgrade feasibility check")
    try:
        httpx_info = fetch_latest("httpx")
        print(f"[monitor] Latest httpx: {httpx_info.latest}")
        with tempfile.TemporaryDirectory() as tmp:
            py = make_temp_venv(tmp)
            feasible = attempt_install(py, httpx_info.latest)
        if not feasible:
            print("[monitor] Upgrade still blocked; exiting.")
            return 0
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY")  # e.g. owner/name
        if token and repo:
            if not find_existing_issue(repo, token):
                create_issue(repo, token, httpx_info.latest)
            else:
                print("[monitor] Issue already exists; no new issue created.")
        else:
            print(
                "[monitor] Missing GITHUB_TOKEN or GITHUB_REPOSITORY; skipping issue creation."
            )
        return 1
    except Exception as e:  # pragma: no cover (best-effort monitoring)
        print(f"[monitor] Script error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
