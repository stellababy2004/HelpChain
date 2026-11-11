import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.security_release_gate_collect import (
    collect_required_evidence,
    collect_alerts,
    validate_sarif,
    validate_artifact_metadata,
    validate_workflow_run,
    safe_zip_members,
    sanitize_gitleaks_report,
    GitHubApiError,
    select_latest_run,
)

SCRIPT = Path("scripts/security_release_gate.py")
BASELINE = {
    "schemaVersion": 1,
    "repository": "stellababy2004/HelpChain",
    "source": "github-code-scanning-api",
    "capturedAt": "2026-11-10",
    "alert_numbers": [1],
    "alert_records": [
        {
            "number": 1,
            "signature": "CodeQL|py/test-rule|backend/app.py|1|head123|high|open",
        }
    ],
}


def run_gate(tmp_path, baseline, alerts, *extra):
    baseline_path = tmp_path / "baseline.json"
    alerts_path = tmp_path / "alerts.json"
    output_path = tmp_path / "report.json"
    status_path = tmp_path / "scan-status.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    alerts_path.write_text(json.dumps(alerts), encoding="utf-8")
    if not status_path.exists():
        status_path.write_text(
            json.dumps(
                [
                    {
                        "name": "codeql",
                        "status": "success",
                        "report_present": True,
                        "report_valid": True,
                        "run_id": "codeql:head123",
                        "head_sha": "head123",
                        "event": "pull_request",
                    }
                ]
            ),
            encoding="utf-8",
        )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline",
            str(baseline_path),
            "--alerts",
            str(alerts_path),
            "--output",
            str(output_path),
            "--repository",
            "stellababy2004/HelpChain",
            "--head-sha",
            "head123",
            "--base-sha",
            "base123",
            "--scan-status",
            str(status_path),
            *extra,
        ],
        check=False,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


class FakeGitHubClient:
    def __init__(self, payloads, artifact_zip):
        self.payloads = payloads
        self.artifact_zip = artifact_zip

    def get(self, path):
        return self.payloads[path]

    def get_paginated(self, path, key):
        if path in self.payloads:
            return self.payloads[path].get(key, [])
        for stored_path, payload in self.payloads.items():
            if stored_path.startswith(path):
                return payload.get(key, [])
        raise KeyError(path)

    def download_artifact(self, artifact_id, destination):
        destination.write_bytes(self.artifact_zip.read_bytes())


def test_collector_downloads_validated_artifact_and_reaches_evidence_output(tmp_path):
    head_sha = "a" * 40
    report = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Trivy"}},
                "results": [{"ruleId": "TRIVY-001", "level": "error", "locations": []}],
            }
        ],
    }
    report_path = tmp_path / "report.sarif"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    zip_path = tmp_path / "report.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(report_path, "report.sarif")
    run = {
        "id": 42,
        "run_attempt": 1,
        "workflow_id": 7,
        "status": "completed",
        "conclusion": "success",
        "head_sha": head_sha,
        "event": "pull_request",
        "repository": {"full_name": "stellababy2004/HelpChain"},
        "pull_requests": [{"head": {"sha": head_sha}}],
    }
    artifact = {
        "id": 99,
        "name": "trivy-iac-sarif",
        "expired": False,
        "workflow_run": {
            "id": 42,
            "run_attempt": 1,
            "repository": {"full_name": "stellababy2004/HelpChain"},
            "head_sha": head_sha,
            "workflow_id": 7,
        },
    }
    payloads = {
        "actions/workflows": {
            "workflows": [
                {"id": 7, "name": "Trivy Security Scan"},
            ]
        },
        f"actions/workflows/7/runs?head_sha={head_sha}&event=pull_request&per_page=100": {
            "workflow_runs": [run]
        },
        "actions/runs/42": run,
        "actions/runs/42/artifacts": {"artifacts": [artifact]},
    }
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    evidence = collect_required_evidence(
        FakeGitHubClient(payloads, zip_path),
        head_sha=head_sha,
        base_sha="b" * 40,
        repository="stellababy2004/HelpChain",
        temp_root=evidence_root,
    )
    trivy = next(
        item for item in evidence["statuses"] if item["name"] == "trivy-iac-sarif"
    )
    assert trivy["report_valid"] is True
    assert trivy["run_id"] == 42
    assert evidence["findings"][0]["rule"] == "TRIVY-001"
    assert evidence["findings"][0]["head_sha"] == head_sha


def test_gitleaks_sanitizer_excludes_secret_payload(tmp_path):
    sanitized = sanitize_gitleaks_report(
        [
            {
                "RuleID": "generic-api-key",
                "File": "config.py",
                "StartLine": 4,
                "Secret": "DO-NOT-EXPORT",
            }
        ],
        head_sha="a" * 40,
    )
    encoded = json.dumps(sanitized)
    assert "DO-NOT-EXPORT" not in encoded
    assert "config.py" not in encoded
    assert sanitized["findings"][0]["rule"] == "generic-api-key"


def test_gitleaks_sanitizer_rejects_malformed_report():
    with pytest.raises(ValueError):
        sanitize_gitleaks_report({"Secret": "DO-NOT-EXPORT"}, head_sha="a" * 40)


def test_newer_in_progress_attempt_rejects_older_success():
    selected = select_latest_run(
        [
            {
                "id": 1,
                "run_attempt": 1,
                "status": "completed",
                "conclusion": "success",
                "updated_at": "2026-11-10T10:00:00Z",
            },
            {
                "id": 2,
                "run_attempt": 2,
                "status": "in_progress",
                "conclusion": None,
                "updated_at": "2026-11-10T11:00:00Z",
            },
        ]
    )
    assert selected["id"] == 2
    assert selected["status"] == "in_progress"


def test_ambiguous_latest_attempt_is_rejected():
    with pytest.raises(GitHubApiError):
        select_latest_run(
            [
                {"id": 1, "run_attempt": 2, "updated_at": "2026-11-10T11:00:00Z"},
                {"id": 2, "run_attempt": 2, "updated_at": "2026-11-10T11:00:00Z"},
            ]
        )


def test_missing_run_attempt_is_rejected_without_defaulting_to_first_attempt():
    with pytest.raises(
        GitHubApiError, match="workflow run attempt metadata unavailable"
    ):
        select_latest_run(
            [
                {
                    "id": 1,
                    "status": "completed",
                    "conclusion": "success",
                    "updated_at": "2026-11-10T11:00:00Z",
                }
            ]
        )


def test_github_pagination_rejects_partial_shape():
    class PagingClient:
        def get(self, path):
            return {"unexpected": []}

    with pytest.raises(GitHubApiError):
        PagingClient().get_paginated = None
        from scripts.security_release_gate_collect import GitHubClient

        GitHubClient.get_paginated(PagingClient(), "actions/runs", "workflow_runs")


def test_codeql_ambiguous_analysis_is_incomplete():
    head_sha = "a" * 40
    run = {"id": 42, "run_attempt": 1, "event": "pull_request"}
    client = FakeGitHubClient(
        {
            f"code-scanning/analyses?ref={head_sha}": {
                "analyses": [
                    {
                        "id": 1,
                        "workflow_run_id": 42,
                        "commit_sha": head_sha,
                        "tool": {"name": "CodeQL"},
                    },
                    {
                        "id": 2,
                        "workflow_run_id": 42,
                        "commit_sha": head_sha,
                        "tool": {"name": "CodeQL"},
                    },
                ]
            }
        },
        Path("missing.zip"),
    )
    from scripts.security_release_gate_collect import collect_codeql_analysis

    result = collect_codeql_analysis(
        client, run=run, head_sha=head_sha, repository="stellababy2004/HelpChain"
    )
    assert result["status"]["status"] == "missing"
    assert result["status"]["report_valid"] is False


def alert(number, severity="high", commit_sha="head123", state="open"):
    return {
        "number": number,
        "state": state,
        "tool": {"name": "CodeQL"},
        "rule": {"id": "py/test-rule", "security_severity_level": severity},
        "most_recent_instance": {
            "location": {"path": "backend/app.py", "start_line": number},
            "commit_sha": commit_sha,
        },
    }


def test_new_high_is_fail(tmp_path):
    report = run_gate(
        tmp_path,
        BASELINE,
        [alert(2)],
        "--api-ok",
    )
    assert report["status"] == "FAIL"
    assert report["new_critical_high_count"] == 1


def test_existing_high_passes_without_new_alert(tmp_path):
    report = run_gate(
        tmp_path,
        BASELINE,
        [alert(1)],
        "--api-ok",
    )
    assert report["status"] == "PASS"
    assert report["new_alert_count"] == 0


def test_unclassified_is_reported_not_silently_low(tmp_path):
    report = run_gate(
        tmp_path,
        BASELINE,
        [alert(1, "unknown")],
        "--api-ok",
    )
    assert report["severity_counts"]["unclassified"] == 1


def test_api_failure_is_incomplete(tmp_path):
    report = run_gate(tmp_path, BASELINE, [])
    assert report["status"] == "INCOMPLETE"


def test_invalid_baseline_is_incomplete(tmp_path):
    report = run_gate(tmp_path, {"source": "other"}, [], "--api-ok")
    assert report["status"] == "INCOMPLETE"


def test_missing_sarif_report_is_incomplete(tmp_path):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps([{"name": "codeql", "status": "missing", "report_present": False}]),
        encoding="utf-8",
    )
    report = run_gate(
        tmp_path,
        BASELINE,
        [],
        "--api-ok",
        "--scan-status",
        str(status_path),
    )
    assert report["status"] == "INCOMPLETE"


def test_invalid_secret_scan_artifact_is_incomplete(tmp_path):
    report_path = tmp_path / "gitleaks.json"
    report_path.write_text(
        json.dumps(
            [
                {
                    "name": "gitleaks-sanitized-json",
                    "status": "failed",
                    "report_present": True,
                    "report_valid": False,
                    "run_id": 42,
                    "head_sha": "head123",
                    "event": "pull_request",
                }
            ]
        ),
        encoding="utf-8",
    )
    result = run_gate(
        tmp_path,
        BASELINE,
        [],
        "--api-ok",
        "--scan-status",
        str(report_path),
    )
    assert result["status"] == "INCOMPLETE"


def test_valid_artifact_provenance_is_accepted():
    result = validate_artifact_metadata(
        {
            "id": 9,
            "name": "bandit-sarif",
            "expired": False,
            "workflow_run": {
                "id": 42,
                "run_attempt": 2,
                "repository": {"full_name": "stellababy2004/HelpChain"},
                "head_sha": "a" * 40,
                "workflow_id": 7,
            },
        },
        repository="stellababy2004/HelpChain",
        run_id=42,
        run_attempt=2,
        artifact_id=9,
        artifact_name="bandit-sarif",
        expected_head_sha="a" * 40,
        workflow_id=7,
    )
    assert result["valid"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 10),
        ("run_attempt", 1),
        ("head_sha", "b" * 40),
    ],
)
def test_wrong_artifact_provenance_is_rejected(field, value):
    source = {
        "id": 42,
        "run_attempt": 2,
        "repository": {"full_name": "stellababy2004/HelpChain"},
        "head_sha": "a" * 40,
        "workflow_id": 7,
    }
    if field in {"run_attempt", "head_sha"}:
        source[field] = value
    metadata = {
        "id": value if field == "id" else 9,
        "name": "bandit-sarif",
        "expired": False,
        "workflow_run": source,
    }
    result = validate_artifact_metadata(
        metadata,
        repository="stellababy2004/HelpChain",
        run_id=42,
        run_attempt=2,
        artifact_id=9,
        artifact_name="bandit-sarif",
        expected_head_sha="a" * 40,
        workflow_id=7,
    )
    assert result["valid"] is False


def test_failed_scanner_is_incomplete(tmp_path):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps([{"name": "trivy", "status": "failed", "report_present": True}]),
        encoding="utf-8",
    )
    report = run_gate(
        tmp_path,
        BASELINE,
        [],
        "--api-ok",
        "--scan-status",
        str(status_path),
    )
    assert report["status"] == "INCOMPLETE"


def test_successful_empty_scan_is_pass(tmp_path):
    report = run_gate(
        tmp_path,
        BASELINE,
        [],
        "--api-ok",
    )
    assert report["status"] == "PASS"


def test_unknown_reachability_requires_review(tmp_path):
    report = run_gate(
        tmp_path,
        BASELINE,
        [alert(99, severity="medium")],
        "--api-ok",
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["reachability"] == "unknown"


def test_wrong_commit_sha_is_incomplete(tmp_path):
    report = run_gate(
        tmp_path, BASELINE, [alert(2, commit_sha="different")], "--api-ok"
    )
    assert report["status"] == "INCOMPLETE"


def test_duplicate_baseline_ids_are_incomplete(tmp_path):
    report = run_gate(tmp_path, {**BASELINE, "alert_numbers": [1, 1]}, [], "--api-ok")
    assert report["status"] == "INCOMPLETE"


def test_reopened_alert_is_not_accepted_by_number_only(tmp_path):
    report = run_gate(tmp_path, BASELINE, [alert(1, state="reopened")], "--api-ok")
    assert report["status"] == "FAIL"
    assert report["new_alert_count"] == 1


def test_malformed_pagination_is_rejected(tmp_path):
    pages = tmp_path / "pages.json"
    output = tmp_path / "alerts.json"
    pages.write_text(json.dumps({"not": "pages"}), encoding="utf-8")
    with pytest.raises(ValueError):
        collect_alerts(pages, output)


def test_dependency_findings_require_review(tmp_path):
    (tmp_path / "scan-status.json").write_text(
        json.dumps(
            [
                {
                    "name": "pip-audit api/requirements.txt",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": "pip-audit:head123",
                    "head_sha": "head123",
                    "event": "pull_request",
                    "findings_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(tmp_path, BASELINE, [], "--api-ok")
    assert report["status"] == "REVIEW REQUIRED"


def test_trusted_workflow_does_not_use_pull_request_target_or_pr_checkout():
    workflow = Path(".github/workflows/security-release-gate-trusted.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request_target" not in workflow
    assert "github.event.repository.default_branch" in workflow
    assert "github.event.pull_request.head.sha" not in workflow


def test_reporting_workflow_is_explicitly_non_authoritative():
    workflow = Path(".github/workflows/security-release-gate.yml").read_text(
        encoding="utf-8"
    )
    assert "Security release gate diagnostics (non-authoritative)" in workflow
    assert "Diagnostic mode: this job is non-authoritative" in workflow
    assert (
        "Authoritative verdict source: Security Release Gate (trusted evaluator)."
        in workflow
    )
    assert "name: security-release-gate-diagnostics" in workflow


def test_trusted_workflow_runs_collector_and_evaluator():
    workflow = Path(".github/workflows/security-release-gate-trusted.yml").read_text(
        encoding="utf-8"
    )
    assert "security_release_gate_collect.py collect-evidence" in workflow
    assert "security_release_gate.py" in workflow
    for scanner in (
        "CodeQL Advanced Security",
        "Trivy Security Scan",
        "Security Scans (Bandit & pip-audit)",
        "Secret Scan",
    ):
        assert scanner in workflow


def test_trusted_workflow_requires_valid_collector_evidence():
    workflow = Path(".github/workflows/security-release-gate-trusted.yml").read_text(
        encoding="utf-8"
    )
    assert "--scanner-findings .scanner-findings.json" in workflow
    assert "--scan-status .security-scan-status.json" in workflow
    assert "collector failed" in workflow
    assert "report_valid" in workflow


def test_missing_scanner_evidence_cannot_pass(tmp_path):
    (tmp_path / "scan-status.json").write_text(
        json.dumps(
            [
                {
                    "name": "Trivy SARIF artifacts",
                    "status": "missing",
                    "report_present": False,
                    "report_valid": False,
                    "run_id": None,
                    "head_sha": None,
                    "event": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(tmp_path, BASELINE, [], "--api-ok")
    assert report["status"] == "INCOMPLETE"


def test_workflow_run_identity_mismatch_is_invalid():
    run = {
        "id": 10,
        "workflow_id": 20,
        "run_attempt": 1,
        "repository": {"full_name": "stellababy2004/HelpChain"},
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "head_sha": "head123",
    }
    pr = {
        "number": 7,
        "head": {"sha": "different"},
        "base": {
            "sha": "base123",
            "repo": {"full_name": "stellababy2004/HelpChain"},
        },
    }
    result = validate_workflow_run(
        run,
        pr,
        repository="stellababy2004/HelpChain",
        workflow_id=20,
        run_id=10,
        run_attempt=1,
        pr_number=7,
        head_sha="head123",
        base_sha="base123",
    )
    assert result["valid"] is False
    assert "PR head SHA mismatch" in result["errors"]


def test_sarif_identity_and_schema_are_validated():
    valid = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Trivy"}}, "results": []}],
    }
    assert validate_sarif(valid, scanner="Trivy", head_sha="head123")["valid"]
    invalid = {"version": "2.1.0", "runs": []}
    assert not validate_sarif(invalid, scanner="Trivy", head_sha="head123")["valid"]


def test_artifact_metadata_must_match_source_run():
    metadata = {
        "id": 5,
        "name": "bandit.sarif",
        "expired": False,
        "workflow_run": {
            "id": 10,
            "run_attempt": 2,
            "repository": {"full_name": "stellababy2004/HelpChain"},
        },
    }
    assert validate_artifact_metadata(
        metadata,
        repository="stellababy2004/HelpChain",
        run_id=10,
        run_attempt=2,
        artifact_id=5,
        artifact_name="bandit.sarif",
    )["valid"]
    assert not validate_artifact_metadata(
        metadata,
        repository="other/repo",
        run_id=10,
        run_attempt=2,
        artifact_id=5,
        artifact_name="bandit.sarif",
    )["valid"]


def test_artifact_without_run_attempt_is_rejected_even_with_trusted_run():
    metadata = {
        "id": 5,
        "name": "bandit.sarif",
        "expired": False,
        "workflow_run": {
            "id": 10,
            "repository": {"full_name": "stellababy2004/HelpChain"},
        },
    }
    trusted_run = {
        "id": 10,
        "run_attempt": 2,
        "head_sha": "head123",
        "workflow_id": 20,
        "repository": {"full_name": "stellababy2004/HelpChain"},
    }
    result = validate_artifact_metadata(
        metadata,
        repository="stellababy2004/HelpChain",
        run_id=10,
        run_attempt=2,
        artifact_id=5,
        artifact_name="bandit.sarif",
        expected_head_sha="head123",
        workflow_id=20,
        trusted_run=trusted_run,
    )
    assert result["valid"] is False
    assert "artifact run attempt metadata unavailable" in result["errors"]


def test_artifact_from_previous_run_attempt_is_rejected():
    metadata = {
        "id": 5,
        "name": "bandit.sarif",
        "expired": False,
        "workflow_run": {
            "id": 10,
            "run_attempt": 1,
            "repository": {"full_name": "stellababy2004/HelpChain"},
        },
    }
    trusted_run = {
        "id": 10,
        "run_attempt": 2,
        "head_sha": "head123",
        "workflow_id": 20,
        "repository": {"full_name": "stellababy2004/HelpChain"},
    }
    result = validate_artifact_metadata(
        metadata,
        repository="stellababy2004/HelpChain",
        run_id=10,
        run_attempt=2,
        artifact_id=5,
        artifact_name="bandit.sarif",
        expected_head_sha="head123",
        workflow_id=20,
        trusted_run=trusted_run,
    )
    assert result["valid"] is False
    assert "artifact run attempt mismatch" in result["errors"]


def test_zip_path_traversal_is_rejected(tmp_path):
    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.json", "{}")
    with pytest.raises(ValueError, match="path traversal"):
        safe_zip_members(archive)
