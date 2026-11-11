"""Validate and normalize GitHub API pagination for the release gate."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

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


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str, repository: str):
        self.token = token
        self.repository = repository

    def get(self, path: str):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path.lstrip('/')}",
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

    def get_paginated(self, path: str, key: str) -> list[dict[str, Any]]:
        items = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            values = payload.get(key)
            if not isinstance(values, list):
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
                urllib.request.urlopen(request, timeout=60) as response,
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
        result["findings"] = extract_sarif_findings(
            report, scanner=scanner, head_sha=head_sha
        )
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
        result = {
            "valid": True,
            "findings_count": sum(
                len(item.get("vulns", []))
                for item in report.get("dependencies", [])
                if isinstance(item, dict)
            ),
            "head_sha": head_sha,
            "findings": extract_pip_audit_findings(
                report, scanner=scanner, head_sha=head_sha
            ),
        }
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
) -> dict[str, Any]:
    workflows = client.get_paginated("actions/workflows", "workflows")
    statuses = []
    findings = []
    for workflow_name in EXPECTED_WORKFLOWS:
        workflow = next(
            (item for item in workflows if item.get("name") == workflow_name), None
        )
        if not workflow:
            statuses.append(
                {
                    "name": workflow_name,
                    "status": "missing",
                    "report_valid": False,
                    "reason": "workflow not found",
                }
            )
            continue
        runs = client.get_paginated(
            f"actions/workflows/{workflow['id']}/runs?head_sha={head_sha}&event=pull_request",
            "workflow_runs",
        )
        candidates = [
            run
            for run in runs
            if run.get("head_sha") == head_sha
            and run.get("event") == "pull_request"
            and any(
                item.get("head", {}).get("sha") == head_sha
                for item in run.get("pull_requests", [])
            )
        ]
        run = select_latest_run(candidates)
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
                        "artifact_id": artifact["id"],
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
            int(item.get("run_attempt", 0) or 0),
            item.get("updated_at", ""),
            item.get("id", 0),
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
    analyses = client.get_paginated(
        f"code-scanning/analyses?ref={head_sha}", "analyses"
    )
    matches = [
        analysis
        for analysis in analyses
        if analysis.get("commit_sha") == head_sha
        and analysis.get("workflow_run_id") == run.get("id")
        and analysis.get("tool", {}).get("name") == "CodeQL"
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
        or not analysis.get("category")
        or analysis.get("analysis_status") != "complete"
    ):
        raise GitHubApiError("CodeQL analysis metadata is incomplete")
    alerts = client.get_paginated(
        f"code-scanning/alerts?state=open&ref={head_sha}", "alerts"
    )
    findings = []
    for alert in alerts:
        instance = alert.get("most_recent_instance", {})
        findings.append(
            {
                "scanner": "CodeQL",
                "rule": alert.get("rule", {}).get("id"),
                "severity": alert.get("rule", {}).get(
                    "security_severity_level", "unclassified"
                ),
                "path": instance.get("location", {}).get("path"),
                "identity": alert.get("number"),
                "head_sha": head_sha,
                "analysis_id": analysis.get("id"),
            }
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
        if not rule:
            raise ValueError("Gitleaks finding lacks safe identifying metadata")
        findings.append(
            {
                "scanner": "Gitleaks",
                "rule": str(rule),
                "severity": "high",
                "line": int(line) if isinstance(line, int) else None,
                "identity": f"{rule}:{line}",
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
            findings.append(
                {
                    "scanner": scanner,
                    "rule": result.get("ruleId"),
                    "severity": str(result.get("level", "unclassified")).lower(),
                    "path": location.get("artifactLocation", {}).get("uri"),
                    "identity": result.get("fingerprints")
                    or result.get("partialFingerprints"),
                    "tool": tool.get("name"),
                    "head_sha": head_sha,
                }
            )
    return findings


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
) -> dict[str, Any]:
    errors = []
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
    if run.get("head_sha") != head_sha:
        errors.append("run head SHA mismatch")
    if pr.get("number") != pr_number:
        errors.append("PR number mismatch")
    if pr.get("base", {}).get("sha") != base_sha:
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


def collect_pip_audit(report_path: Path, output_path: Path, status_code: int) -> None:
    try:
        report = read(report_path)
        if not isinstance(report, dict) or not isinstance(
            report.get("dependencies"), list
        ):
            raise ValueError("invalid pip-audit JSON")
        findings_count = sum(
            len(item.get("vulns", item.get("vulnerabilities", [])))
            for item in report["dependencies"]
            if isinstance(item, dict)
        )
        value = {
            "name": "pip-audit api/requirements.txt",
            "status": "success" if status_code in (0, 1) else "failed",
            "report_present": True,
            "report_valid": True,
            "findings_count": findings_count,
        }
    except (OSError, ValueError, json.JSONDecodeError):
        value = {
            "name": "pip-audit api/requirements.txt",
            "status": "failed",
            "report_present": report_path.exists(),
            "report_valid": False,
            "findings_count": 0,
        }
    write(output_path, [value])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(
            "alerts",
            "runs",
            "pip-audit",
            "validate-run",
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
    if args.mode == "alerts":
        collect_alerts(args.pages, args.output)
    elif args.mode == "runs":
        collect_runs(args.pages, args.output, args.expected_head_sha)
    elif args.mode == "pip-audit":
        collect_pip_audit(args.pages, args.output, args.status_code)
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
