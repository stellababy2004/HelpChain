"""Validate and normalize GitHub API pagination for the release gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCANNERS = (
    "CodeQL Advanced Security",
    "Trivy Security Scan",
    "Security Scans (Bandit & pip-audit)",
    "Secret Scan",
)

EXPECTED_EVIDENCE = {
    "Trivy Security Scan": [
        ("trivy-iac-sarif", "Trivy"),
        ("trivy-repo-sarif", "Trivy"),
    ],
    "Security Scans (Bandit & pip-audit)": [
        ("bandit-sarif", "Bandit"),
        ("pip-audit-runtime-baseline", "pip-audit"),
    ],
    "Security Release Gate (reporting)": [("pip-audit-api-json", "pip-audit")],
    "Secret Scan": [("gitleaks-results.sarif", "Gitleaks")],
}

EXPECTED_WORKFLOWS = (
    "CodeQL Advanced Security",
    "Trivy Security Scan",
    "Security Scans (Bandit & pip-audit)",
    "Secret Scan",
)


# Expected jobs are part of the trusted scanner contract, including matrix names.
SCANNER_WORKFLOWS = {
    "CodeQL Advanced Security": ("codeql-analysis.yml", {"Analyze (python)": ()}),
    "Trivy Security Scan": (
        "trivy-scan.yml",
        {
            "Trivy IaC Scan": ("trivy-iac-sarif",),
            "Trivy Repository Scan": ("trivy-repo-sarif",),
        },
    ),
    "Security Scans (Bandit & pip-audit)": (
        "security-scans.yml",
        {
            "Bandit (SAST)": ("bandit-sarif",),
            "pip-audit (Dependencies)": ("pip-audit-runtime-baseline",),
        },
    ),
    "Secret Scan": ("secret-scan.yml", {"scan": ("gitleaks-results.sarif",)}),
}
CHECKOUT_ACTION = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"


class GitHubApiError(RuntimeError):
    pass


SHA1_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


class SafeArtifactRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent forwarding GitHub credentials to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit

        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None

        original = urlsplit(req.full_url)
        target = urlsplit(newurl)

        if original.scheme.lower() != "https" or target.scheme.lower() != "https":
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "unsafe artifact redirect scheme",
                headers,
                fp,
            )
        if not target.hostname:
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "artifact redirect has no hostname",
                headers,
                fp,
            )

        if (original.hostname or "").lower() != (target.hostname or "").lower():
            for key in list(redirected.headers):
                if key.lower() in ("authorization", "proxy-authorization"):
                    del redirected.headers[key]

            for key in list(redirected.unredirected_hdrs):
                if key.lower() in ("authorization", "proxy-authorization"):
                    del redirected.unredirected_hdrs[key]

        return redirected


class GitHubClient:
    def __init__(self, token: str, repository: str):
        self.token = token
        self.repository = repository
        self._job_logs: dict[str, str] = {}

    def get(self, path: str):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}"
            + (f"/{path.lstrip('/')}" if path else ""),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            raise GitHubApiError(
                f"GitHub API request failed: {type(exc).__name__}"
            ) from exc

    def get_text(self, path: str) -> str:
        """Read completed job logs without forwarding credentials across redirects."""
        if path not in self._job_logs:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{self.repository}/{path}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            try:
                with urllib.request.build_opener(SafeArtifactRedirectHandler()).open(
                    request, timeout=60
                ) as response:
                    payload = response.read(20_000_001)
                if len(payload) > 20_000_000:
                    raise GitHubApiError("job log exceeds size limit")
                self._job_logs[path] = payload.decode("utf-8-sig")
            except (urllib.error.URLError, UnicodeError) as exc:
                raise GitHubApiError("job log is unavailable or invalid") from exc
        return self._job_logs[path]

    def get_paginated(self, path: str, key: str) -> list[dict[str, Any]]:
        items = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            if isinstance(payload, list) and key in {"analyses", "alerts", "pulls"}:
                values = payload
            elif isinstance(payload, dict) and key not in {
                "analyses",
                "alerts",
                "pulls",
            }:
                values = payload.get(key)
            else:
                values = None
            if not isinstance(values, list) or not all(
                isinstance(item, dict) for item in values
            ):
                raise GitHubApiError(f"invalid paginated response: {key}")
            items.extend(values)
            if len(values) < 100:
                return items
            page += 1

    def download_artifact(self, artifact_id: int, destination: Path) -> None:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/actions/artifacts/{artifact_id}/zip",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with (
                urllib.request.build_opener(SafeArtifactRedirectHandler()).open(
                    request, timeout=60
                ) as response,
                destination.open("wb") as handle,
            ):
                shutil.copyfileobj(response, handle, length=64 * 1024)
        except urllib.error.HTTPError as exc:
            raise GitHubApiError(
                f"artifact download failed: HTTP {exc.code} ({exc.reason})"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise GitHubApiError(
                f"artifact download failed: {type(exc).__name__}"
            ) from exc


def api_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("missing timezone")
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise GitHubApiError("missing or invalid provenance timestamp") from exc


def during_job(timestamp: str, job: dict[str, Any]) -> bool:
    # API step/job timestamps have second precision, whereas logs include fractions.
    return (
        api_time(job.get("started_at"))
        <= api_time(timestamp)
        < api_time(job.get("completed_at")) + timedelta(seconds=1)
    )


def checkout_provenance(
    log: str,
    job: dict[str, Any],
    *,
    repository: str,
    pr_number: int,
    artifact_names: tuple[str, ...],
) -> dict[str, Any]:
    lines = []
    for line in log.splitlines():
        timestamp, separator, message = line.partition(" ")
        if not separator or not re.fullmatch(r"[0-9]{4}-[0-9T:.+-]+Z", timestamp):
            # Scanner output can span unprefixed lines. Such lines cannot prove provenance.
            timestamp, message = None, line
        lines.append((timestamp, message))
    starts = [
        i
        for i, (_, message) in enumerate(lines)
        if message == f"##[group]Run {CHECKOUT_ACTION}"
    ]
    steps = [
        step
        for step in job.get("steps", [])
        if step.get("name") in {"Checkout", "Checkout repository"}
    ]
    if (
        len(starts) != 1
        or len(steps) != 1
        or steps[0].get("number") != 2
        or steps[0].get("status") != "completed"
        or steps[0].get("conclusion") != "success"
    ):
        raise GitHubApiError("missing or ambiguous pinned checkout step")
    start = starts[0]
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i][1].startswith("##[group]Run ")
        ),
        len(lines),
    )
    section = lines[start:end]
    if not all(during_job(timestamp, steps[0]) for timestamp, _ in section):
        raise GitHubApiError("checkout log is outside the verified step")
    if (
        sum(message.strip() == f"repository: {repository}" for _, message in section)
        != 1
    ):
        raise GitHubApiError("checkout repository mismatch")
    refs = [
        message.removeprefix("[command]/usr/bin/git checkout --progress --force ")
        for _, message in section
        if message.startswith("[command]/usr/bin/git checkout --progress --force ")
    ]
    commits = [
        section[i + 1][1]
        for i, (_, message) in enumerate(section[:-1])
        if message == "[command]/usr/bin/git log -1 --format=%H"
    ]
    if len(refs) != 1 or len(commits) != 1 or not SHA1_PATTERN.fullmatch(commits[0]):
        raise GitHubApiError("missing or ambiguous checkout commit/ref")
    ref = refs[0].replace("refs/remotes/pull/", "refs/pull/")
    if ref not in {
        f"refs/pull/{pr_number}/merge",
        f"refs/pull/{pr_number}/head",
        commits[0],
    }:
        raise GitHubApiError("checkout PR ref mismatch")
    artifacts = {}
    for name in artifact_names:
        pattern = re.compile(
            rf"Artifact {re.escape(name)}\.zip successfully finalized\. Artifact ID ([0-9]+)$"
        )
        matches = [
            int(match.group(1))
            for timestamp, message in lines
            if (match := pattern.fullmatch(message)) and during_job(timestamp, job)
        ]
        if len(matches) != 1:
            raise GitHubApiError(f"missing or ambiguous artifact upload in job: {name}")
        artifacts[name] = matches[0]
    return {
        "scanned_sha": commits[0],
        "scanned_ref": ref,
        "artifacts": artifacts,
        "log_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest(),
    }


def scanner_run_provenance(
    client: GitHubClient, run: dict[str, Any], pr: dict[str, Any]
) -> dict[str, Any]:
    name = run.get("name")
    if name not in SCANNER_WORKFLOWS:
        raise GitHubApiError("unexpected scanner workflow")
    filename, expected_jobs = SCANNER_WORKFLOWS[name]
    path = f".github/workflows/{filename}"
    workflow = client.get(f"actions/workflows/{run['workflow_id']}")
    if (
        workflow.get("id") != run["workflow_id"]
        or workflow.get("name") != name
        or workflow.get("path") != path
        or run.get("path") != path
        or run.get("head_branch") != pr.get("head", {}).get("ref")
    ):
        raise GitHubApiError("scanner workflow or PR branch mismatch")
    current = client.get(f"actions/runs/{run['id']}")
    for key in (
        "id",
        "workflow_id",
        "run_attempt",
        "head_sha",
        "event",
        "status",
        "conclusion",
    ):
        if current.get(key) != run.get(key):
            raise GitHubApiError(f"scanner run changed: {key}")
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise GitHubApiError("invalid scanner attempt")
    jobs = client.get_paginated(
        f"actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"
    )
    if len(jobs) != len(expected_jobs) or {job.get("name") for job in jobs} != set(
        expected_jobs
    ):
        raise GitHubApiError("missing or ambiguous scanner jobs")
    observations = []
    for job in jobs:
        if (
            job.get("run_id") != run["id"]
            or job.get("run_attempt") != attempt
            or job.get("head_sha") != run["head_sha"]
            or job.get("run_url")
            != f"https://api.github.com/repos/{client.repository}/actions/runs/{run['id']}"
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
        ):
            raise GitHubApiError("scanner job run/attempt identity mismatch")
        proof = checkout_provenance(
            client.get_text(f"actions/jobs/{job['id']}/logs"),
            job,
            repository=client.repository,
            pr_number=pr["number"],
            artifact_names=expected_jobs[job["name"]],
        )
        observations.append({**job, **proof})
    scanned = {(job["scanned_sha"], job["scanned_ref"]) for job in observations}
    if len(scanned) != 1:
        raise GitHubApiError("scanner jobs checked out conflicting commits or refs")
    sha, ref = scanned.pop()
    return {"scanned_sha": sha, "scanned_ref": ref, "jobs": observations}


def discover_run_artifact(
    client: GitHubClient,
    *,
    run_id: int,
    run_attempt: int,
    artifact_name: str,
    repository: str,
    expected_head_sha: str | None = None,
    expected_event: str | None = None,
    expected_workflow_id: int | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = client.get(f"actions/runs/{run_id}")
    if run.get("id") != run_id or run.get("run_attempt") != run_attempt:
        raise GitHubApiError("workflow run identity mismatch")
    if run.get("repository", {}).get("full_name") != repository:
        raise GitHubApiError("workflow run repository mismatch")
    if expected_head_sha is not None and run.get("head_sha") != expected_head_sha:
        raise GitHubApiError("workflow run SHA mismatch")
    if expected_event is not None and run.get("event") != expected_event:
        raise GitHubApiError("workflow run event mismatch")
    if (
        expected_workflow_id is not None
        and run.get("workflow_id") != expected_workflow_id
    ):
        raise GitHubApiError("workflow run workflow mismatch")
    artifacts = client.get_paginated(f"actions/runs/{run_id}/artifacts", "artifacts")
    matches = [item for item in artifacts if item.get("name") == artifact_name]
    if len(matches) != 1:
        raise GitHubApiError("expected artifact missing or ambiguous")
    artifact = matches[0]
    if provenance is not None:
        producers = [
            job
            for job in provenance["jobs"]
            if job["artifacts"].get(artifact_name) == artifact.get("id")
        ]
        if (
            len(producers) != 1
            or not during_job(artifact.get("created_at"), producers[0])
            or not during_job(artifact.get("updated_at"), producers[0])
        ):
            raise GitHubApiError("artifact does not belong to the verified job attempt")
    metadata_check = validate_artifact_metadata(
        artifact,
        repository=repository,
        run_id=run_id,
        run_attempt=run_attempt,
        artifact_id=artifact["id"],
        artifact_name=artifact_name,
        expected_head_sha=run.get("head_sha"),
        workflow_id=run.get("workflow_id"),
        trusted_run=run,
    )
    if not metadata_check["valid"]:
        raise GitHubApiError("artifact metadata validation failed")
    return artifact


def download_and_validate_artifact(
    client: GitHubClient,
    *,
    artifact: dict[str, Any],
    scanner: str,
    head_sha: str,
    temp_root: Path,
) -> dict[str, Any]:
    zip_path = temp_root / f"{artifact['id']}.zip"
    client.download_artifact(artifact["id"], zip_path)
    digest = artifact.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or hashlib.sha256(
        zip_path.read_bytes()
    ).hexdigest() != digest.removeprefix("sha256:"):
        raise GitHubApiError("artifact archive digest missing or mismatched")
    members = safe_zip_members(zip_path)
    report_members = [name for name in members if name.endswith((".sarif", ".json"))]
    if len(report_members) != 1:
        raise GitHubApiError("artifact must contain exactly one SARIF or JSON report")
    with zipfile.ZipFile(zip_path) as archive:
        report_path = temp_root / report_members[0].replace("/", "_")
        report_path.write_bytes(archive.read(report_members[0]))
    report = read(report_path)
    if report_members[0].endswith(".sarif"):
        result = validate_sarif(report, scanner=scanner, head_sha=head_sha)
        raw_findings = extract_sarif_findings(
            report, scanner=scanner, head_sha=head_sha
        )
        result["raw_findings_count"] = len(raw_findings)
        result["findings"] = deduplicate_findings(raw_findings)
        result["findings_count"] = len(result["findings"])
    elif scanner == "Gitleaks":
        if (
            not isinstance(report, dict)
            or report.get("scanner") != "Gitleaks"
            or report.get("head_sha") != head_sha
            or not isinstance(report.get("findings"), list)
        ):
            raise GitHubApiError("JSON report does not match sanitized Gitleaks schema")
        result = {
            "valid": True,
            "findings_count": len(report["findings"]),
            "head_sha": head_sha,
            "findings": report["findings"],
        }
    elif not isinstance(report, dict) or not isinstance(
        report.get("dependencies"), list
    ):
        raise GitHubApiError("JSON report does not match pip-audit schema")
    else:
        findings = deduplicate_findings(
            extract_pip_audit_findings(report, scanner=scanner, head_sha=head_sha)
        )
        result = {
            "valid": True,
            "findings_count": len(findings),
            "head_sha": head_sha,
            "findings": findings,
        }
        result["raw_findings_count"] = len(result["findings"])
    result["artifact_id"] = artifact["id"]
    result["artifact_name"] = artifact["name"]
    return result


def collect_required_evidence(
    client: GitHubClient,
    *,
    head_sha: str,
    base_sha: str,
    repository: str,
    temp_root: Path,
    pr_head_sha: str | None = None,
) -> dict[str, Any]:
    workflows = client.get_paginated("actions/workflows", "workflows")
    statuses = []
    findings = []
    for workflow_name in EXPECTED_WORKFLOWS:
        matching_workflows = [
            item for item in workflows if item.get("name") == workflow_name
        ]
        if not matching_workflows:
            statuses.append(
                {
                    "name": workflow_name,
                    "status": "missing",
                    "report_valid": False,
                    "reason": "workflow not found",
                }
            )
            continue
        if len(matching_workflows) != 1:
            raise GitHubApiError(f"ambiguous workflow: {workflow_name}")
        workflow = matching_workflows[0]
        runs = {}
        for metadata_sha in dict.fromkeys([pr_head_sha or head_sha, head_sha]):
            for run in client.get_paginated(
                f"actions/workflows/{workflow['id']}/runs?head_sha={metadata_sha}&event=pull_request",
                "workflow_runs",
            ):
                if (
                    run.get("head_sha") == metadata_sha
                    and run.get("event") == "pull_request"
                ):
                    runs[run["id"]] = run
        if not runs and pr_head_sha is None:
            associated = client.get_paginated(f"commits/{head_sha}/pulls", "pulls")
            prs = [client.get(f"pulls/{item['number']}") for item in associated]
            matches = [
                pr
                for pr in prs
                if head_sha
                in {pr.get("head", {}).get("sha"), pr.get("merge_commit_sha")}
                and pr.get("base", {}).get("repo", {}).get("full_name") == repository
            ]
            if len(matches) != 1:
                raise GitHubApiError("missing or ambiguous scanner PR lookup")
            metadata_sha = matches[0]["head"]["sha"]
            for run in client.get_paginated(
                f"actions/workflows/{workflow['id']}/runs?head_sha={metadata_sha}&event=pull_request",
                "workflow_runs",
            ):
                if (
                    run.get("head_sha") == metadata_sha
                    and run.get("event") == "pull_request"
                ):
                    runs[run["id"]] = run
        run = select_latest_run(list(runs.values()))
        identity = None
        if (
            run
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ):
            run = client.get(f"actions/runs/{run['id']}")
            if run.get("workflow_id") != workflow["id"]:
                raise GitHubApiError("scanner workflow ID mismatch")
            identity = resolve_pr_identity(client, run)
            if (
                identity["base_sha"] != base_sha
                or identity["scanned_sha"] != head_sha
                or (pr_head_sha is not None and identity["pr_head_sha"] != pr_head_sha)
            ):
                raise GitHubApiError("scanner PR/base/scanned SHA mismatch")
        if (
            not run
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
        ):
            statuses.append(
                {
                    "name": workflow_name,
                    "status": "incomplete" if run else "missing",
                    "report_valid": False,
                    "run_id": run.get("id") if run else None,
                    "head_sha": run.get("head_sha") if run else None,
                    "reason": "latest exact-head attempt is not a completed success",
                }
            )
            continue
        if workflow_name == "CodeQL Advanced Security":
            codeql = collect_codeql_analysis(
                client, run=run, head_sha=head_sha, repository=repository
            )
            statuses.append(codeql["status"])
            findings.extend(codeql["findings"])
            continue
        artifact_specs = EXPECTED_EVIDENCE.get(workflow_name, [])
        if not artifact_specs:
            statuses.append(
                {
                    "name": workflow_name,
                    "status": "missing",
                    "report_valid": False,
                    "run_id": run["id"],
                    "head_sha": head_sha,
                    "reason": "no trusted machine-readable evidence configured",
                }
            )
            continue
        for artifact_name, scanner in artifact_specs:
            try:
                artifact = discover_run_artifact(
                    client,
                    run_id=run["id"],
                    run_attempt=run["run_attempt"],
                    artifact_name=artifact_name,
                    repository=repository,
                    expected_head_sha=run.get("head_sha"),
                    expected_event="pull_request",
                    expected_workflow_id=run.get("workflow_id"),
                    provenance=identity,
                )
                result = download_and_validate_artifact(
                    client,
                    artifact=artifact,
                    scanner=scanner,
                    head_sha=head_sha,
                    temp_root=temp_root,
                )
                statuses.append(
                    {
                        "name": artifact_name,
                        "status": "success" if result.get("valid") else "failed",
                        "report_present": True,
                        "report_valid": result.get("valid", False),
                        "run_id": run["id"],
                        "run_attempt": run["run_attempt"],
                        "head_sha": head_sha,
                        "event": "pull_request",
                        "findings_count": result.get("findings_count", 0),
                        "raw_findings_count": result.get(
                            "raw_findings_count", result.get("findings_count", 0)
                        ),
                        "artifact_id": artifact["id"],
                        "workflow_run_head_sha": run["head_sha"],
                        "pr_head_sha": identity["pr_head_sha"],
                        "scanned_sha": head_sha,
                        "ref": identity["scanned_ref"],
                    }
                )
                findings.extend(result.get("findings", []))
            except (GitHubApiError, OSError, ValueError, KeyError) as exc:
                statuses.append(
                    {
                        "name": artifact_name,
                        "status": "failed",
                        "report_valid": False,
                        "run_id": run["id"],
                        "head_sha": head_sha,
                        "reason": str(exc),
                    }
                )
    for status in statuses:
        status.setdefault("evidence_class", "workflow_artifact")
    return {
        "statuses": statuses,
        "findings": findings,
        "head_sha": head_sha,
        "base_sha": base_sha,
    }


def select_latest_run(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the newest attempt; callers fail closed unless it succeeded."""
    if not candidates:
        return None
    for candidate in candidates:
        attempt = candidate.get("run_attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise GitHubApiError("workflow run attempt metadata unavailable")
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get("created_at", item.get("updated_at", "")),
            item.get("id", 0),
            int(item.get("run_attempt", 0) or 0),
            item.get("updated_at", ""),
        ),
        reverse=True,
    )
    if len(ordered) > 1 and (
        int(ordered[0].get("run_attempt", 0) or 0)
        == int(ordered[1].get("run_attempt", 0) or 0)
        and ordered[0].get("updated_at") == ordered[1].get("updated_at")
    ):
        raise GitHubApiError("ambiguous latest scanner run")
    return ordered[0]


def collect_codeql_analysis(
    client: GitHubClient,
    *,
    run: dict[str, Any],
    head_sha: str,
    repository: str,
) -> dict[str, Any]:
    identity = resolve_pr_identity(client, run)
    if identity["scanned_sha"] != head_sha or client.repository != repository:
        raise GitHubApiError("CodeQL scanned commit or repository mismatch")
    pr_number = identity["pr_number"]
    expected_ref = identity["scanned_ref"]
    pr = client.get(f"pulls/{pr_number}")
    if pr.get("head", {}).get("sha") != identity["pr_head_sha"]:
        raise GitHubApiError("PR head changed during collection")
    scanned_sha = identity["scanned_sha"]
    analyses = client.get_paginated(
        f"code-scanning/analyses?ref={quote(expected_ref, safe='')}", "analyses"
    )
    analysis_steps = [
        step
        for job in identity["jobs"]
        for step in job.get("steps", [])
        if step.get("name") == "Perform CodeQL Analysis"
        and step.get("conclusion") == "success"
    ]
    if len(analysis_steps) != 1:
        raise GitHubApiError("missing or ambiguous CodeQL analysis step")
    matches = [
        analysis
        for analysis in analyses
        if analysis.get("commit_sha") == scanned_sha
        and during_job(analysis.get("created_at"), analysis_steps[0])
        and analysis.get("tool", {}).get("name") == "CodeQL"
        and analysis.get("ref") == expected_ref
        and analysis.get("analysis_key")
        == ".github/workflows/codeql-analysis.yml:analyze"
        and analysis.get("category") == "/language:python"
    ]
    if len(matches) != 1:
        return {
            "status": {
                "name": "CodeQL analysis",
                "status": "missing",
                "report_present": False,
                "report_valid": False,
                "run_id": run.get("id"),
                "run_attempt": run.get("run_attempt"),
                "head_sha": head_sha,
                "event": run.get("event"),
                "reason": "analysis provenance is missing or ambiguous",
            },
            "findings": [],
        }
    analysis = matches[0]
    if analysis.get("repository", {}).get("full_name", repository) != repository:
        raise GitHubApiError("CodeQL analysis repository mismatch")
    if (
        not analysis.get("id")
        or not analysis.get("analysis_key")
        or not analysis.get("category")
        or "error" not in analysis
        or analysis.get("error") not in ("", None)
    ):
        raise GitHubApiError("CodeQL analysis metadata is incomplete")
    alerts = client.get_paginated(
        f"code-scanning/alerts?state=open&ref={quote(expected_ref, safe='')}", "alerts"
    )
    findings = []
    for alert in alerts:
        if alert.get("tool", {}).get("name") != "CodeQL":
            continue
        instance = alert.get("most_recent_instance", {})
        if (
            instance.get("commit_sha") != head_sha
            or instance.get("ref") != expected_ref
            or instance.get("analysis_key") != analysis["analysis_key"]
            or instance.get("category") != analysis["category"]
        ):
            raise GitHubApiError("CodeQL alert instance is stale or mismatched")
        findings.append(
            {
                "scanner": "CodeQL",
                "rule": alert.get("rule", {}).get("id"),
                "severity": alert.get("rule", {}).get(
                    "security_severity_level", "unclassified"
                ),
                "path": instance.get("location", {}).get("path"),
                "identity": alert.get("number"),
                "line": instance.get("location", {}).get("start_line"),
                "head_sha": head_sha,
                "analysis_id": analysis.get("id"),
            }
        )
    if analysis.get("results_count", 0) and not findings:
        raise GitHubApiError(
            "non-empty CodeQL analysis has no open alert evidence; alert state requires reconciliation"
        )
    return {
        "status": {
            "name": "CodeQL analysis",
            "status": "success",
            "report_present": True,
            "report_valid": True,
            "run_id": run.get("id"),
            "run_attempt": run.get("run_attempt"),
            "head_sha": head_sha,
            "event": run.get("event"),
            "analysis_id": analysis.get("id"),
            "analysis_key": analysis.get("analysis_key"),
            "ref": analysis.get("ref"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "scanned_sha": scanned_sha,
            "workflow_run_head_sha": run["head_sha"],
            "pr_head_sha": identity["pr_head_sha"],
            "findings_count": len(findings),
        },
        "findings": findings,
    }


def sanitize_gitleaks_report(report: Any, *, head_sha: str) -> dict[str, Any]:
    if not isinstance(report, list):
        raise ValueError("Gitleaks report must be a JSON array")
    findings = []
    for item in report:
        if not isinstance(item, dict):
            raise ValueError("invalid Gitleaks finding")
        rule = item.get("RuleID") or item.get("ruleID")
        line = item.get("StartLine") or item.get("startLine")
        path = item.get("File") or item.get("file")
        historical_commit = item.get("Commit") or item.get("commit")
        if (
            not rule
            or not isinstance(path, str)
            or not path
            or not isinstance(historical_commit, str)
            or not SHA1_PATTERN.fullmatch(historical_commit)
        ):
            raise ValueError("Gitleaks finding lacks safe identifying metadata")
        normalized_path = posixpath.normpath(path.replace("\\", "/"))
        if (
            normalized_path in {".", ".."}
            or normalized_path.startswith("../")
            or normalized_path.startswith("/")
        ):
            raise ValueError("Gitleaks finding has an unsafe path")
        findings.append(
            {
                "scanner": "Gitleaks",
                "rule": str(rule),
                "severity": "high",
                "path": normalized_path,
                "line": int(line) if isinstance(line, int) else None,
                "identity": f"{rule}:{line}",
                "historical_commit": historical_commit.lower(),
                "head_sha": head_sha,
            }
        )
    return {
        "schema_version": 1,
        "scanner": "Gitleaks",
        "head_sha": head_sha,
        "findings": findings,
    }


def extract_sarif_findings(
    report: dict[str, Any], *, scanner: str, head_sha: str
) -> list[dict[str, Any]]:
    findings = []
    for run in report.get("runs", []):
        tool = run.get("tool", {}).get("driver", {})
        for result in run.get("results", []):
            location = (result.get("locations") or [{}])[0].get("physicalLocation", {})
            raw_fingerprints = result.get("fingerprints") or result.get(
                "partialFingerprints"
            )
            evidence_fingerprint = None
            fingerprint_commit = None
            if isinstance(raw_fingerprints, dict) and raw_fingerprints:
                encoded = json.dumps(
                    raw_fingerprints, ensure_ascii=False, sort_keys=True
                ).encode("utf-8")
                evidence_fingerprint = "sha256:" + hashlib.sha256(encoded).hexdigest()
                for key, value in raw_fingerprints.items():
                    if str(key).lower() in {"commitsha", "commit_sha", "commit"}:
                        if isinstance(value, str) and SHA1_PATTERN.fullmatch(value):
                            fingerprint_commit = value.lower()
                            break
            properties = result.get("properties")
            property_commit = (
                properties.get("commit_sha") or properties.get("commit")
                if isinstance(properties, dict)
                else None
            )
            historical_commit = (
                property_commit
                if isinstance(property_commit, str)
                and SHA1_PATTERN.fullmatch(property_commit)
                else fingerprint_commit
            )
            rule = result.get("ruleId")
            line = location.get("region", {}).get("startLine")
            findings.append(
                {
                    "scanner": scanner,
                    "rule": rule,
                    "severity": str(result.get("level", "unclassified")).lower(),
                    "path": location.get("artifactLocation", {}).get("uri"),
                    "line": line,
                    "identity": (
                        f"{rule}:{line}"
                        if scanner.lower() == "gitleaks"
                        else evidence_fingerprint
                    ),
                    "evidence_fingerprint": evidence_fingerprint,
                    "historical_commit": historical_commit,
                    "tool": tool.get("name"),
                    "head_sha": head_sha,
                }
            )
    return findings


def evidence_finding_key(finding: dict[str, Any]) -> str | None:
    scanner = finding.get("scanner")
    rule = finding.get("rule")
    path = finding.get("path")
    line = finding.get("line")
    package = finding.get("package")
    if not isinstance(scanner, str) or not isinstance(rule, str):
        return None
    if isinstance(path, str) and isinstance(line, int) and not isinstance(line, bool):
        base = f"{scanner.lower()}|{rule.lower()}|{path}|{line}"
    elif isinstance(package, str) and package:
        base = f"{scanner.lower()}|{rule.lower()}|package:{package.lower()}"
    else:
        return None
    fingerprint = finding.get("evidence_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return f"{base}|{fingerprint}"
    return base


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    seen = set()
    for finding in findings:
        key = evidence_finding_key(finding)
        if key is None or key not in seen:
            unique.append(finding)
            if key is not None:
                seen.add(key)
    return unique


def extract_pip_audit_findings(
    report: dict[str, Any], *, scanner: str, head_sha: str
) -> list[dict[str, Any]]:
    findings = []
    for dependency in report.get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        for vulnerability in dependency.get(
            "vulns", dependency.get("vulnerabilities", [])
        ):
            if isinstance(vulnerability, dict):
                findings.append(
                    {
                        "scanner": scanner,
                        "rule": vulnerability.get("id"),
                        "severity": str(
                            vulnerability.get("severity", "unclassified")
                        ).lower(),
                        "package": dependency.get("name"),
                        "identity": vulnerability.get("id"),
                        "head_sha": head_sha,
                    }
                )
    return findings


def read(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def verify_base_ancestry(
    client: GitHubClient, pr: dict[str, Any], scan_base: str, snapshot_base: str | None
) -> None:
    """Anchor the scan parent and PR snapshots to the repository default branch."""
    repository = client.get("")
    branch = repository.get("default_branch")
    if (
        repository.get("full_name") != client.repository
        or not isinstance(branch, str)
        or not branch
        or pr.get("base", {}).get("ref") != branch
    ):
        raise GitHubApiError("PR base is not the trusted default branch")
    trusted = (
        client.get(f"branches/{quote(branch, safe='')}").get("commit", {}).get("sha")
    )
    if not isinstance(trusted, str) or not SHA1_PATTERN.fullmatch(trusted):
        raise GitHubApiError("missing or invalid trusted branch SHA")

    def ancestor(older: str, newer: str) -> bool:
        if older == newer:
            return True
        comparison = client.get(f"compare/{older}...{newer}")
        return (
            comparison.get("status") in {"ahead", "identical"}
            and comparison.get("merge_base_commit", {}).get("sha") == older
            and comparison.get("base_commit", {}).get("sha") == older
        )

    if not ancestor(scan_base, trusted):
        raise GitHubApiError("scanned base is outside trusted default branch ancestry")
    for base in dict.fromkeys([pr["base"]["sha"], snapshot_base]):
        if base is None:
            continue
        if not isinstance(base, str) or not SHA1_PATTERN.fullmatch(base):
            raise GitHubApiError("invalid PR base snapshot SHA")
        if not ancestor(base, trusted) or not (
            ancestor(base, scan_base) or ancestor(scan_base, base)
        ):
            raise GitHubApiError("PR base snapshot has unrelated trusted ancestry")


def resolve_pr_identity(client: GitHubClient, run: dict[str, Any]) -> dict[str, Any]:
    """Resolve current PR metadata and prove its relationship to the scanned commit."""
    sha = run.get("head_sha", "")
    if not isinstance(sha, str) or not SHA1_PATTERN.fullmatch(sha):
        raise GitHubApiError("invalid scanned SHA")
    if (
        run.get("event") != "pull_request"
        or run.get("repository", {}).get("full_name") != client.repository
        or run.get("head_repository", {}).get("full_name") != client.repository
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise GitHubApiError("unsuccessful or mismatched upstream run")
    attached = run.get("pull_requests")
    if not isinstance(attached, list) or len(attached) > 1:
        raise GitHubApiError("ambiguous upstream PR identity")
    candidates = attached
    if not candidates:
        candidates = client.get_paginated(f"commits/{sha}/pulls", "pulls")
    # Every candidate is re-read to reject stale list metadata and moved heads.
    matches = []
    rejections = []
    for candidate in candidates:
        number = candidate.get("number")
        if type(number) is not int or number <= 0:
            raise GitHubApiError("invalid PR number")
        pr = client.get(f"pulls/{number}")
        if pr.get("number") != number:
            raise GitHubApiError("PR number mismatch")
        head = pr.get("head", {}).get("sha", "")
        base = pr.get("base", {}).get("sha", "")
        if (
            pr.get("head", {}).get("repo", {}).get("full_name") != client.repository
            or pr.get("base", {}).get("repo", {}).get("full_name") != client.repository
            or not SHA1_PATTERN.fullmatch(str(head))
            or not SHA1_PATTERN.fullmatch(str(base))
        ):
            rejections.append(f"PR #{number}: repository or SHA mismatch")
            continue
        merged = pr.get("state") == "closed" and pr.get("merged") is True
        if pr.get("state") != "open" and not merged:
            rejections.append(f"PR #{number}: closed without merging")
            continue
        snapshot_base = None
        if attached:
            snapshot_head = candidate.get("head", {}).get("sha")
            snapshot_base = candidate.get("base", {}).get("sha")
            if snapshot_head is not None and snapshot_head != head:
                rejections.append(f"PR #{number}: attached PR head snapshot changed")
                continue
        if sha not in {head, pr.get("merge_commit_sha")}:
            rejections.append(
                f"PR #{number}: run metadata SHA is unrelated to current PR"
            )
            continue
        provenance = scanner_run_provenance(client, run, pr)
        scanned_sha = provenance["scanned_sha"]
        commit = None
        if scanned_sha == head:
            if merged or provenance["scanned_ref"] not in {
                head,
                f"refs/pull/{number}/head",
            }:
                continue
            scan_base = base
        elif scanned_sha == pr.get("merge_commit_sha"):
            if provenance["scanned_ref"] != f"refs/pull/{number}/merge":
                rejections.append(f"PR #{number}: merge checkout ref mismatch")
                continue
            commit = client.get(f"commits/{scanned_sha}")
            parents = [item.get("sha") for item in commit.get("parents", [])]
            if (
                commit.get("sha") != scanned_sha
                or len(parents) != 2
                or parents[1] != head
                or not SHA1_PATTERN.fullmatch(str(parents[0]))
                or parents[0] == head
            ):
                rejections.append(f"PR #{number}: scanned merge parents mismatch")
                continue
            scan_base = parents[0]
        else:
            rejections.append(
                f"PR #{number}: checkout commit is unrelated to current PR"
            )
            continue
        verify_base_ancestry(client, pr, scan_base, snapshot_base)
        filename = SCANNER_WORKFLOWS[run["name"]][0]
        workflow_path = f".github/workflows/{filename}"
        trusted_source = client.get(f"contents/{workflow_path}?ref={scan_base}")
        scanned_source = client.get(f"contents/{workflow_path}?ref={scanned_sha}")
        if (
            trusted_source.get("type") != "file"
            or scanned_source.get("type") != "file"
            or trusted_source.get("path") != workflow_path
            or scanned_source.get("path") != workflow_path
            or not SHA1_PATTERN.fullmatch(str(trusted_source.get("sha", "")))
            or scanned_source.get("sha") != trusted_source["sha"]
        ):
            raise GitHubApiError("scanner workflow differs from trusted base source")
        validation = validate_workflow_run(
            run,
            pr,
            repository=client.repository,
            workflow_id=run.get("workflow_id"),
            run_id=run.get("id"),
            run_attempt=run.get("run_attempt"),
            pr_number=number,
            head_sha=head,
            base_sha=scan_base,
            scanned_sha=scanned_sha,
            scanned_commit=commit,
            workflow_run_head_sha=sha,
            base_ancestry_verified=True,
        )
        if not validation["valid"]:
            rejections.append(f"PR #{number}: " + ", ".join(validation["errors"]))
            continue
        matches.append(
            {
                "pr_number": number,
                "pr_head_sha": head,
                "scanned_sha": scanned_sha,
                "workflow_run_head_sha": sha,
                "scanned_ref": provenance["scanned_ref"],
                "jobs": provenance["jobs"],
                "base_sha": scan_base,
            }
        )
    if len(matches) != 1:
        detail = "; ".join(rejections) or f"{len(matches)} valid PR matches"
        raise GitHubApiError(f"missing, stale, or ambiguous PR identity: {detail}")
    return matches[0]


def validate_workflow_run(
    run: dict[str, Any],
    pr: dict[str, Any],
    *,
    repository: str,
    workflow_id: int,
    run_id: int,
    run_attempt: int,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    scanned_sha: str | None = None,
    scanned_commit: dict[str, Any] | None = None,
    workflow_run_head_sha: str | None = None,
    base_ancestry_verified: bool = False,
) -> dict[str, Any]:
    errors = []
    scanned_sha = scanned_sha or head_sha
    if run.get("id") != run_id:
        errors.append("run ID mismatch")
    if run.get("workflow_id") != workflow_id:
        errors.append("workflow ID mismatch")
    if run.get("run_attempt") != run_attempt:
        errors.append("run attempt mismatch")
    if run.get("repository", {}).get("full_name") != repository:
        errors.append("run repository mismatch")
    if run.get("event") != "pull_request":
        errors.append("unexpected event type")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        errors.append("run is not completed successfully")
    if run.get("head_sha") != (workflow_run_head_sha or scanned_sha):
        errors.append("run metadata SHA mismatch")
    if run.get("head_sha") not in {head_sha, pr.get("merge_commit_sha")}:
        errors.append("run metadata is unrelated to the PR")
    if pr.get("number") != pr_number:
        errors.append("PR number mismatch")
    merged = pr.get("state") == "closed" and pr.get("merged") is True
    if pr.get("state") != "open" and not merged:
        errors.append("PR is closed without merging")
    if pr.get("head", {}).get("repo", {}).get("full_name") != repository:
        errors.append("head repository mismatch")
    if scanned_sha != head_sha:
        parents = [
            item.get("sha") for item in (scanned_commit or {}).get("parents", [])
        ]
        if (
            pr.get("merge_commit_sha") != scanned_sha
            or (scanned_commit or {}).get("sha") != scanned_sha
            or parents != [base_sha, head_sha]
        ):
            errors.append("scanned merge relationship mismatch")
    elif merged:
        errors.append("merged PR requires merge commit evidence")
    if (
        not base_ancestry_verified
        and (not merged or scanned_sha == head_sha)
        and pr.get("base", {}).get("sha") != base_sha
    ):
        errors.append("PR base SHA mismatch")
    if pr.get("head", {}).get("sha") != head_sha:
        errors.append("PR head SHA mismatch")
    if pr.get("base", {}).get("repo", {}).get("full_name") != repository:
        errors.append("base repository mismatch")
    return {
        "valid": not errors,
        "errors": errors,
        "run_id": run_id,
        "run_attempt": run_attempt,
    }


def validate_sarif(
    report: dict[str, Any], *, scanner: str, head_sha: str
) -> dict[str, Any]:
    errors = []
    if report.get("version") != "2.1.0":
        errors.append("unsupported SARIF version")
    runs = report.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("missing SARIF runs")
    finding_count = 0
    if isinstance(runs, list):
        for item in runs:
            if not isinstance(item, dict):
                errors.append("invalid SARIF run")
                continue
            tool_name = item.get("tool", {}).get("driver", {}).get("name")
            if scanner.lower() not in str(tool_name).lower():
                errors.append("scanner identity mismatch")
            results = item.get("results", [])
            if not isinstance(results, list):
                errors.append("invalid SARIF results")
            else:
                finding_count += len(results)
                for result in results:
                    if not isinstance(result, dict):
                        errors.append("invalid SARIF result")
                        continue
                    for fingerprint_key in ("fingerprints", "partialFingerprints"):
                        fingerprints = result.get(fingerprint_key)
                        if fingerprints is not None and (
                            not isinstance(fingerprints, dict)
                            or not all(
                                isinstance(key, str) and isinstance(value, str)
                                for key, value in fingerprints.items()
                            )
                        ):
                            errors.append(f"invalid SARIF {fingerprint_key}")
    return {
        "valid": not errors,
        "errors": errors,
        "findings_count": finding_count,
        "head_sha": head_sha,
    }


def validate_artifact_metadata(
    metadata: dict[str, Any],
    *,
    repository: str,
    run_id: int,
    run_attempt: int,
    artifact_id: int,
    artifact_name: str,
    expected_head_sha: str | None = None,
    workflow_id: int | None = None,
    trusted_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors = []
    if metadata.get("id") != artifact_id:
        errors.append("artifact ID mismatch")
    if metadata.get("name") != artifact_name:
        errors.append("artifact name mismatch")
    if metadata.get("expired") is True:
        errors.append("artifact expired")
    source = metadata.get("workflow_run", {})
    if trusted_run is not None:
        for field, expected in (
            ("repository_id", trusted_run.get("repository", {}).get("id")),
            ("head_repository_id", trusted_run.get("head_repository", {}).get("id")),
            ("head_branch", trusted_run.get("head_branch")),
        ):
            if field in source and source[field] != expected:
                errors.append(f"artifact source {field} mismatch")
    if source.get("id") != run_id:
        errors.append("artifact source run mismatch")
    source_attempt = source.get("run_attempt")
    trusted_run_id = trusted_run.get("id") if trusted_run else None
    if source_attempt is None and trusted_run_id == run_id:
        source_attempt = trusted_run.get("run_attempt")
    if source_attempt is None:
        errors.append("artifact run attempt metadata unavailable")
    elif source_attempt != run_attempt:
        errors.append("artifact run attempt mismatch")
    source_repository = source.get("repository", {}).get("full_name")
    if source_repository is None and trusted_run is not None:
        source_repository = trusted_run.get("repository", {}).get("full_name")
    if source_repository != repository:
        errors.append("artifact repository mismatch")
    source_sha = source.get("head_sha")
    if source_sha is None and trusted_run is not None:
        source_sha = trusted_run.get("head_sha")
    if expected_head_sha is not None and source_sha != expected_head_sha:
        errors.append("artifact source SHA mismatch")
    source_workflow = source.get("workflow_id")
    if source_workflow is None and trusted_run is not None:
        source_workflow = trusted_run.get("workflow_id")
    if workflow_id is not None and source_workflow != workflow_id:
        errors.append("artifact source workflow mismatch")
    return {"valid": not errors, "errors": errors}


def safe_zip_members(
    zip_path: Path, *, max_files: int = 50, max_total_size: int = 20_000_000
) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > max_files:
            raise ValueError("artifact contains too many files")
        total_size = 0
        safe_names = []
        for member in members:
            name = member.filename.replace("\\", "/")
            normalized = posixpath.normpath(name)
            if (
                name.startswith("/")
                or normalized == ".."
                or normalized.startswith("../")
            ):
                raise ValueError("artifact path traversal")
            if member.is_dir():
                continue
            total_size += member.file_size
            if member.file_size > max_total_size or total_size > max_total_size:
                raise ValueError("artifact exceeds decompression limits")
            safe_names.append(normalized)
        return safe_names


def collect_alerts(pages_path: Path, output_path: Path) -> None:
    pages = read(pages_path)
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise ValueError("invalid paginated alerts response")
    alerts = [item for page in pages for item in page]
    write(output_path, alerts)


def collect_runs(pages_path: Path, output_path: Path, expected_head_sha: str) -> None:
    pages = read(pages_path)
    if not isinstance(pages, list) or not all(isinstance(page, dict) for page in pages):
        raise ValueError("invalid paginated workflow response")
    runs = [run for page in pages for run in page.get("workflow_runs", [])]
    statuses = []
    for name in SCANNERS:
        matches = [
            run
            for run in runs
            if run.get("name") == name
            and run.get("head_sha") == expected_head_sha
            and run.get("event") == "pull_request"
        ]
        completed = [run for run in matches if run.get("status") == "completed"]
        latest = (
            sorted(completed, key=lambda run: run.get("updated_at", ""), reverse=True)[
                0
            ]
            if completed
            else None
        )
        statuses.append(
            {
                "name": name,
                "status": (
                    "success"
                    if latest and latest.get("conclusion") == "success"
                    else ("failed" if latest else "missing")
                ),
                "report_present": bool(latest),
                "report_valid": False,
                "run_id": latest.get("id") if latest else None,
                "head_sha": latest.get("head_sha") if latest else None,
                "event": latest.get("event") if latest else None,
                "ref": latest.get("head_branch") if latest else None,
            }
        )
    write(output_path, statuses)


def collect_pip_audit(
    report_path: Path,
    output_path: Path,
    status_code: int,
    findings_output: Path | None = None,
) -> None:
    try:
        report = read(report_path)
        if not isinstance(report, dict) or not isinstance(
            report.get("dependencies"), list
        ):
            raise ValueError("invalid pip-audit JSON")
        findings = extract_pip_audit_findings(
            report, scanner="pip-audit", head_sha=None
        )
        findings = deduplicate_findings(findings)
        value = {
            "name": "pip-audit api/requirements.txt",
            "evidence_class": "local_dependency_check",
            "status": "success" if status_code in (0, 1) else "failed",
            "report_present": True,
            "report_valid": True,
            "findings_count": len(findings),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        value = {
            "name": "pip-audit api/requirements.txt",
            "evidence_class": "local_dependency_check",
            "status": "failed",
            "report_present": report_path.exists(),
            "report_valid": False,
            "findings_count": 0,
        }
        findings = []
    write(output_path, [value])
    if findings_output:
        write(findings_output, findings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(
            "alerts",
            "runs",
            "pip-audit",
            "validate-run",
            "resolve-pr",
            "validate-sarif",
            "validate-artifact",
            "zip-members",
            "download-artifact",
            "collect-evidence",
            "sanitize-gitleaks",
            "merge",
        ),
    )
    parser.add_argument("--pages", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-status", type=Path)
    parser.add_argument("--scanner-status", type=Path)
    parser.add_argument("--expected-head-sha")
    parser.add_argument("--status-code", type=int, default=2)
    parser.add_argument("--run-json", type=Path)
    parser.add_argument("--pr-json", type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--workflow-id", type=int)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--run-attempt", type=int)
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--head-sha")
    parser.add_argument("--pr-head-sha")
    parser.add_argument("--base-sha")
    parser.add_argument("--scanner")
    parser.add_argument("--artifact-json", type=Path)
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--artifact-name")
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN"))
    parser.add_argument("--temp-root", type=Path)
    parser.add_argument("--findings-output", type=Path)
    args = parser.parse_args()
    if args.mode == "resolve-pr":
        client = GitHubClient(args.token, args.repository)
        run = client.get(f"actions/runs/{args.run_id}")
        if (
            run.get("id") != args.run_id
            or run.get("run_attempt") != args.run_attempt
            or run.get("workflow_id") != args.workflow_id
            or run.get("head_sha") != args.head_sha
        ):
            raise GitHubApiError("upstream run identity mismatch")
        identity = resolve_pr_identity(client, run)
        write(args.output, identity)
    elif args.mode == "alerts":
        collect_alerts(args.pages, args.output)
    elif args.mode == "runs":
        collect_runs(args.pages, args.output, args.expected_head_sha)
    elif args.mode == "pip-audit":
        collect_pip_audit(
            args.pages, args.output, args.status_code, args.findings_output
        )
    elif args.mode == "validate-run":
        result = validate_workflow_run(
            read(args.run_json),
            read(args.pr_json),
            repository=args.repository,
            workflow_id=args.workflow_id,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            base_sha=args.base_sha,
        )
        write(args.output, result)
    elif args.mode == "validate-sarif":
        write(
            args.output,
            validate_sarif(
                read(args.pages), scanner=args.scanner, head_sha=args.head_sha
            ),
        )
    elif args.mode == "validate-artifact":
        write(
            args.output,
            validate_artifact_metadata(
                read(args.artifact_json),
                repository=args.repository,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                artifact_id=args.artifact_id,
                artifact_name=args.artifact_name,
            ),
        )
    elif args.mode == "zip-members":
        write(args.output, {"valid": True, "members": safe_zip_members(args.zip)})
    elif args.mode == "download-artifact":
        client = GitHubClient(args.token, args.repository)
        artifact = discover_run_artifact(
            client,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            artifact_name=args.artifact_name,
            repository=args.repository,
        )
        with tempfile.TemporaryDirectory(dir=args.temp_root) as root:
            result = download_and_validate_artifact(
                client,
                artifact=artifact,
                scanner=args.scanner,
                head_sha=args.head_sha,
                temp_root=Path(root),
            )
        write(args.output, result)
    elif args.mode == "collect-evidence":
        client = GitHubClient(args.token, args.repository)
        if not args.temp_root:
            raise ValueError("--temp-root is required for collect-evidence")
        args.temp_root.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=args.temp_root) as root:
                evidence = collect_required_evidence(
                    client,
                    head_sha=args.head_sha,
                    pr_head_sha=args.pr_head_sha,
                    base_sha=args.base_sha,
                    repository=args.repository,
                    temp_root=Path(root),
                )
        except (
            GitHubApiError,
            OSError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            evidence = {
                "statuses": [
                    {
                        "name": "scanner-evidence-collection",
                        "status": "missing",
                        "report_present": False,
                        "report_valid": False,
                        "reason": str(exc),
                    }
                ],
                "findings": [],
            }
        write(args.output, evidence["statuses"])
        if args.findings_output:
            write(args.findings_output, evidence["findings"])
    elif args.mode == "sanitize-gitleaks":
        write(
            args.output,
            sanitize_gitleaks_report(read(args.pages), head_sha=args.head_sha),
        )
    else:
        write(args.output, read(args.api_status) + read(args.scanner_status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
