import json
import subprocess
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

from scripts.security_release_gate_collect import (
    collect_required_evidence,
    collect_alerts,
    collect_pip_audit,
    deduplicate_findings,
    extract_sarif_findings,
    validate_sarif,
    validate_artifact_metadata,
    validate_workflow_run,
    safe_zip_members,
    sanitize_gitleaks_report,
    GitHubApiError,
    GitHubClient,
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
                        "run_attempt": 1,
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


def run_disposition_gate(tmp_path, findings, *, disposition_path=None, status=None):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps(
            status
            or [
                {
                    "name": "bandit-sarif",
                    "evidence_class": "workflow_artifact",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": 42,
                    "run_attempt": 1,
                    "head_sha": "head123",
                    "event": "pull_request",
                    "findings_count": len(findings),
                }
            ]
        ),
        encoding="utf-8",
    )
    findings_path = tmp_path / "scanner-findings.json"
    findings_path.write_text(json.dumps(findings), encoding="utf-8")
    args = (
        "--api-ok",
        "--scan-status",
        str(status_path),
        "--scanner-findings",
        str(findings_path),
    )
    if disposition_path is not None:
        args += ("--dispositions", str(disposition_path))
    return run_gate(tmp_path, BASELINE, [], *args)


def reviewed_findings():
    return [
        {
            "scanner": "Bandit",
            "rule": "B104",
            "severity": "unclassified",
            "path": "backend/helpchain_backend/src/extensions.py",
            "line": 23,
            "identity": "bandit-b104-extensions-23",
            "head_sha": "head123",
        },
        {
            "scanner": "Bandit",
            "rule": "B104",
            "severity": "unclassified",
            "path": "backend/helpchain_backend/src/routes/admin.py",
            "line": 2148,
            "identity": "bandit-b104-admin-2148",
            "head_sha": "head123",
        },
        {
            "scanner": "Gitleaks",
            "rule": "secret-key-assignment",
            "severity": "unclassified",
            "path": "tests/test_sensitive_logging_remediation.py",
            "line": 140,
            "identity": "secret-key-assignment:140",
            "historical_commit": "07fa68d170c91db30392b5322e756dbf09ef6529",
            "head_sha": "head123",
        },
    ]


def disposition_copy(tmp_path, mutate=None):
    source = Path("docs/security/PR-203-FINDINGS-DISPOSITIONS-2026-11-11.json")
    document = json.loads(source.read_text(encoding="utf-8"))
    if mutate:
        mutate(document)
    path = tmp_path / "dispositions.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


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


def test_artifact_redirect_does_not_forward_authorization_cross_host():
    import urllib.request

    from scripts.security_release_gate_collect import SafeArtifactRedirectHandler

    handler = SafeArtifactRedirectHandler()
    original = urllib.request.Request(
        "https://api.github.com/repos/example/repo/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer test-token"},
    )

    redirected = handler.redirect_request(
        original,
        None,
        302,
        "Found",
        {},
        "https://artifact-storage.example.com/download",
    )

    assert redirected is not None
    assert not redirected.has_header("Authorization")


def test_artifact_redirect_preserves_authorization_same_host():
    import urllib.request

    from scripts.security_release_gate_collect import SafeArtifactRedirectHandler

    handler = SafeArtifactRedirectHandler()
    original = urllib.request.Request(
        "https://api.github.com/repos/example/repo/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer test-token"},
    )

    redirected = handler.redirect_request(
        original,
        None,
        302,
        "Found",
        {},
        "https://api.github.com/another-path",
    )

    assert redirected is not None
    assert redirected.has_header("Authorization")


def test_artifact_redirect_rejects_http_downgrade():
    import urllib.request

    from scripts.security_release_gate_collect import SafeArtifactRedirectHandler

    handler = SafeArtifactRedirectHandler()
    original = urllib.request.Request(
        "https://api.github.com/repos/example/repo/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer test-token"},
    )

    with pytest.raises(urllib.error.HTTPError, match="unsafe artifact redirect scheme"):
        handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "http://artifact-storage.example.com/download",
        )


def test_collector_downloads_validated_artifact_and_reaches_evidence_output(tmp_path):
    head_sha = "a" * 40
    report = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Trivy"}},
                "results": [
                    {
                        "ruleId": "TRIVY-001",
                        "level": "error",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "iac/main.tf"},
                                    "region": {"startLine": 7},
                                }
                            }
                        ],
                    }
                ],
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
    assert evidence["findings"][0]["line"] == 7
    assert evidence["findings"][0]["head_sha"] == head_sha


def test_gitleaks_sanitizer_excludes_secret_payload(tmp_path):
    sanitized = sanitize_gitleaks_report(
        [
            {
                "RuleID": "generic-api-key",
                "File": "config.py",
                "StartLine": 4,
                "Commit": "a" * 40,
                "Secret": "DO-NOT-EXPORT",
            }
        ],
        head_sha="a" * 40,
    )
    encoded = json.dumps(sanitized)
    assert "DO-NOT-EXPORT" not in encoded
    assert sanitized["findings"][0]["path"] == "config.py"
    assert sanitized["findings"][0]["historical_commit"] == "a" * 40
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
    merge_sha = "c" * 40
    run = {
        "id": 42,
        "run_attempt": 1,
        "event": "pull_request",
        "pull_requests": [{"number": 203, "head": {"sha": head_sha}}],
    }
    client = FakeGitHubClient(
        {
            "code-scanning/analyses?ref=refs/pull/203/merge": {
                "analyses": [
                    {
                        "id": 1,
                        "workflow_run_id": 42,
                        "commit_sha": merge_sha,
                        "ref": "refs/pull/203/merge",
                        "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
                        "category": "/language:python",
                        "error": "",
                        "tool": {"name": "CodeQL"},
                    },
                    {
                        "id": 2,
                        "workflow_run_id": 42,
                        "commit_sha": merge_sha,
                        "ref": "refs/pull/203/merge",
                        "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
                        "category": "/language:python",
                        "error": "",
                        "tool": {"name": "CodeQL"},
                    },
                ],
            },
            "pulls/203": {
                "number": 203,
                "head": {
                    "sha": head_sha,
                    "repo": {"full_name": "stellababy2004/HelpChain"},
                },
                "base": {
                    "repo": {"full_name": "stellababy2004/HelpChain"},
                },
                "merge_commit_sha": merge_sha,
            },
        },
        Path("missing.zip"),
    )
    from scripts.security_release_gate_collect import collect_codeql_analysis

    result = collect_codeql_analysis(
        client, run=run, head_sha=head_sha, repository="stellababy2004/HelpChain"
    )
    assert result["status"]["status"] == "missing"
    assert result["status"]["report_valid"] is False


def test_codeql_analysis_with_exact_pr_ref_and_sha_is_valid():
    head_sha = "b" * 40
    merge_sha = "c" * 40
    run = {
        "id": 42,
        "run_attempt": 1,
        "event": "pull_request",
        "pull_requests": [{"number": 203, "head": {"sha": head_sha}}],
    }
    client = FakeGitHubClient(
        {
            "code-scanning/analyses?ref=refs/pull/203/merge": {
                "analyses": [
                    {
                        "id": 3,
                        "commit_sha": merge_sha,
                        "ref": "refs/pull/203/merge",
                        "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
                        "category": "/language:python",
                        "error": "",
                        "tool": {"name": "CodeQL"},
                    }
                ]
            },
            f"code-scanning/alerts?state=open&ref={head_sha}": {"alerts": []},
            "pulls/203": {
                "number": 203,
                "head": {
                    "sha": head_sha,
                    "repo": {"full_name": "stellababy2004/HelpChain"},
                },
                "base": {
                    "repo": {"full_name": "stellababy2004/HelpChain"},
                },
                "merge_commit_sha": merge_sha,
            },
        },
        Path("missing.zip"),
    )
    from scripts.security_release_gate_collect import collect_codeql_analysis

    result = collect_codeql_analysis(
        client, run=run, head_sha=head_sha, repository="stellababy2004/HelpChain"
    )
    assert result["status"]["status"] == "success"
    assert result["status"]["report_valid"] is True
    assert result["status"]["analysis_id"] == 3


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
                    "name": "gitleaks-results.sarif",
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


def test_codeql_analysis_top_level_list_is_accepted(monkeypatch):
    from scripts.security_release_gate_collect import GitHubClient

    analysis = {
        "id": 1,
        "commit_sha": "head123",
        "workflow_run_id": 42,
        "tool": {"name": "CodeQL"},
    }
    client = GitHubClient("token", "stellababy2004/HelpChain")
    monkeypatch.setattr(client, "get", lambda path: [analysis])

    assert client.get_paginated("code-scanning/analyses?ref=head123", "analyses") == [
        analysis
    ]


def test_code_scanning_alerts_top_level_list_is_accepted(monkeypatch):
    alerts = [{"number": 1, "state": "open"}]
    client = GitHubClient("token", "stellababy2004/HelpChain")
    monkeypatch.setattr(client, "get", lambda path: alerts)

    assert client.get_paginated("code-scanning/alerts?state=open", "alerts") == alerts


def test_code_scanning_alerts_pagination_is_preserved(monkeypatch):
    first_page = [{"number": index} for index in range(100)]
    second_page = [{"number": 100}]
    pages = {
        "code-scanning/alerts?state=open&per_page=100&page=1": first_page,
        "code-scanning/alerts?state=open&per_page=100&page=2": second_page,
    }
    client = GitHubClient("token", "stellababy2004/HelpChain")
    monkeypatch.setattr(client, "get", pages.__getitem__)

    assert client.get_paginated("code-scanning/alerts?state=open", "alerts") == (
        first_page + second_page
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"alerts": []},
        {"message": "Not Found", "documentation_url": "https://docs.github.com"},
        ["unexpected-shape"],
    ],
)
def test_code_scanning_alerts_malformed_response_is_rejected(monkeypatch, payload):
    client = GitHubClient("token", "stellababy2004/HelpChain")
    monkeypatch.setattr(client, "get", lambda path: payload)

    with pytest.raises(GitHubApiError, match="invalid paginated response: alerts"):
        client.get_paginated("code-scanning/alerts?state=open", "alerts")


def test_sarif_fingerprints_disambiguate_same_location_without_exposing_metadata():
    report = {
        "runs": [
            {
                "tool": {"driver": {"name": "Gitleaks"}},
                "results": [
                    {
                        "ruleId": "secret-key-assignment",
                        "level": "warning",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": "tests/test_sensitive_logging_remediation.py"
                                    },
                                    "region": {"startLine": 140},
                                }
                            }
                        ],
                        "fingerprints": {
                            "commitSha": "a" * 40,
                            "commitMessage": "opaque historical metadata",
                        },
                    },
                    {
                        "ruleId": "secret-key-assignment",
                        "level": "warning",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": "tests/test_sensitive_logging_remediation.py"
                                    },
                                    "region": {"startLine": 140},
                                }
                            }
                        ],
                        "fingerprints": {
                            "commitSha": "b" * 40,
                            "commitMessage": "different opaque metadata",
                        },
                    },
                ],
            }
        ]
    }
    findings = extract_sarif_findings(report, scanner="Gitleaks", head_sha="c" * 40)
    assert findings[0]["historical_commit"] == "a" * 40
    assert findings[1]["historical_commit"] == "b" * 40
    assert findings[0]["identity"] == "secret-key-assignment:140"
    assert findings[0]["evidence_fingerprint"].startswith("sha256:")
    assert "opaque historical metadata" not in json.dumps(findings)
    assert len(deduplicate_findings(findings)) == 2
    assert len(deduplicate_findings(findings + [findings[0]])) == 2


def test_local_pip_audit_findings_are_emitted_without_workflow_provenance(tmp_path):
    report_path = tmp_path / "pip-audit.json"
    status_path = tmp_path / "status.json"
    findings_path = tmp_path / "findings.json"
    report_path.write_text(
        json.dumps(
            {
                "dependencies": [
                    {
                        "name": "Werkzeug",
                        "vulns": [{"id": "CVE-1", "severity": "high"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    collect_pip_audit(report_path, status_path, 1, findings_path)
    status = json.loads(status_path.read_text(encoding="utf-8"))
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    assert status[0]["evidence_class"] == "local_dependency_check"
    assert status[0]["findings_count"] == 1
    assert findings[0]["package"] == "Werkzeug"
    assert findings[0]["head_sha"] is None


def test_local_dependency_findings_reconcile_without_count_mismatch(tmp_path):
    findings = [
        {
            "scanner": "pip-audit",
            "rule": "CVE-1",
            "severity": "unclassified",
            "package": "Werkzeug",
        }
    ]
    report = run_disposition_gate(
        tmp_path,
        findings,
        status=[
            {
                "name": "pip-audit api/requirements.txt",
                "evidence_class": "local_dependency_check",
                "status": "success",
                "report_present": True,
                "report_valid": True,
                "findings_count": 1,
                "run_id": None,
                "run_attempt": None,
                "head_sha": None,
                "event": None,
            }
        ],
    )
    assert report["scanner_complete"] is True
    assert (
        "scanner finding count does not match evidence counts"
        not in report["disposition_errors"]
    )


def test_dependency_findings_require_review(tmp_path):
    (tmp_path / "scan-status.json").write_text(
        json.dumps(
            [
                {
                    "name": "pip-audit api/requirements.txt",
                    "evidence_class": "local_dependency_check",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "findings_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(tmp_path, BASELINE, [], "--api-ok")
    assert report["status"] == "REVIEW REQUIRED"


def test_exact_owner_dispositions_recognize_findings_without_removing_evidence(
    tmp_path,
):
    findings = reviewed_findings()
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] == "PASS"
    assert report["recognized_disposition_count"] == 3
    assert report["unresolved_dispositions"] == []
    assert len(report["scanner_findings"]) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        lambda finding: finding.update({"path": "backend/other.py"}),
        lambda finding: finding.update({"rule": "B999"}),
        lambda finding: finding.update({"line": 24}),
        lambda finding: finding.update({"severity": "high"}),
    ],
)
def test_new_or_changed_finding_is_not_authorized(tmp_path, mutation):
    findings = reviewed_findings()
    mutation(findings[0])
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] in {"REVIEW REQUIRED", "FAIL"}
    assert report["recognized_disposition_count"] < 3


def test_missing_owner_disposition_fails_closed(tmp_path):
    report = run_disposition_gate(
        tmp_path,
        reviewed_findings(),
        disposition_path=tmp_path / "missing.json",
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 0


def test_unknown_scanner_rule_is_not_accepted(tmp_path):
    findings = reviewed_findings()
    findings[0]["rule"] = "B999"
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert any(
        item["reason"] == "no exact disposition"
        for item in report["unresolved_dispositions"]
    )


def test_historical_gitleaks_disposition_cannot_authorize_other_credential(tmp_path):
    findings = reviewed_findings()
    findings[2]["rule"] = "generic-api-key"
    findings[2]["path"] = "config/settings.py"
    findings[2]["line"] = 11
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_historical_gitleaks_commit_mismatch_fails_closed(tmp_path):
    path = disposition_copy(
        tmp_path,
        lambda document: document["dispositions"][2].update(
            {"historical_commit": "0" * 40}
        ),
    )
    report = run_disposition_gate(
        tmp_path,
        reviewed_findings(),
        disposition_path=path,
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_same_location_with_changed_context_digest_is_not_authorized(tmp_path):
    path = disposition_copy(
        tmp_path,
        lambda document: document["dispositions"][0].update(
            {"context_digest": "sha256:" + "0" * 64}
        ),
    )
    report = run_disposition_gate(
        tmp_path,
        reviewed_findings(),
        disposition_path=path,
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_same_location_with_changed_gitleaks_commit_is_not_authorized(tmp_path):
    findings = reviewed_findings()
    findings[2]["historical_commit"] = "a" * 40
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_same_location_with_changed_gitleaks_fingerprint_is_not_authorized(tmp_path):
    findings = reviewed_findings()
    findings[2]["evidence_fingerprint"] = "sha256:" + "f" * 64
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_invalid_or_expired_disposition_fails_closed(tmp_path):
    path = disposition_copy(
        tmp_path,
        lambda document: document["dispositions"][0].update(
            {"expires_on": "2020-01-01"}
        ),
    )
    report = run_disposition_gate(
        tmp_path,
        reviewed_findings(),
        disposition_path=path,
    )
    assert report["status"] == "REVIEW REQUIRED"
    assert report["recognized_disposition_count"] == 2


def test_scanner_completeness_remains_mandatory_with_valid_dispositions(tmp_path):
    findings = reviewed_findings()
    report = run_disposition_gate(
        tmp_path,
        findings,
        disposition_path=disposition_copy(tmp_path),
        status=[
            {
                "name": "bandit-sarif",
                "evidence_class": "workflow_artifact",
                "status": "missing",
                "report_present": False,
                "report_valid": False,
                "findings_count": 3,
            }
        ],
    )
    assert report["status"] == "INCOMPLETE"
    assert report["scanner_complete"] is False


def test_baseline_validation_remains_mandatory_with_valid_dispositions(tmp_path):
    report = run_disposition_gate(
        tmp_path,
        reviewed_findings(),
        disposition_path=disposition_copy(tmp_path),
    )
    assert report["baseline_valid"] is True
    invalid_dir = tmp_path / "invalid-baseline"
    invalid_dir.mkdir()
    invalid = run_gate(
        invalid_dir,
        {"source": "other"},
        [],
        "--api-ok",
    )
    assert invalid["status"] == "INCOMPLETE"


def test_local_dependency_check_without_workflow_provenance_can_complete(tmp_path):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps(
            [
                {
                    "name": "pip-audit api/requirements.txt",
                    "evidence_class": "local_dependency_check",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "findings_count": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(
        tmp_path, BASELINE, [], "--api-ok", "--scan-status", str(status_path)
    )
    assert report["scanner_complete"] is True
    assert report["status"] == "PASS"


def test_local_dependency_check_with_workflow_provenance_is_incomplete(tmp_path):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps(
            [
                {
                    "name": "pip-audit api/requirements.txt",
                    "evidence_class": "local_dependency_check",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": "fabricated-run",
                    "head_sha": "head123",
                    "event": "pull_request",
                    "findings_count": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(
        tmp_path, BASELINE, [], "--api-ok", "--scan-status", str(status_path)
    )
    assert report["scanner_complete"] is False
    assert report["status"] == "INCOMPLETE"


def test_code_scanning_api_evidence_with_exact_head_is_complete(tmp_path):
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(
        json.dumps(
            [
                {
                    "name": "github-code-scanning-api",
                    "evidence_class": "code_scanning_api",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": "code-scanning-api:head123",
                    "run_attempt": None,
                    "head_sha": "head123",
                    "event": "pull_request",
                }
            ]
        ),
        encoding="utf-8",
    )
    report = run_gate(
        tmp_path, BASELINE, [], "--api-ok", "--scan-status", str(status_path)
    )
    assert report["scanner_complete"] is True
    assert report["status"] == "PASS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "code-scanning-api:otherhead"),
        ("run_attempt", 1),
        ("head_sha", "otherhead"),
        ("event", "workflow_dispatch"),
    ],
)
def test_code_scanning_api_invalid_provenance_is_incomplete(tmp_path, field, value):
    status = {
        "name": "github-code-scanning-api",
        "evidence_class": "code_scanning_api",
        "status": "success",
        "report_present": True,
        "report_valid": True,
        "run_id": "code-scanning-api:head123",
        "run_attempt": None,
        "head_sha": "head123",
        "event": "pull_request",
    }
    status[field] = value
    status_path = tmp_path / "scan-status.json"
    status_path.write_text(json.dumps([status]), encoding="utf-8")
    report = run_gate(
        tmp_path, BASELINE, [], "--api-ok", "--scan-status", str(status_path)
    )
    assert report["scanner_complete"] is False
    assert report["status"] == "INCOMPLETE"


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


def test_malformed_sarif_fingerprints_are_rejected():
    malformed = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Gitleaks"}},
                "results": [{"fingerprints": ["not-an-object"]}],
            }
        ],
    }
    result = validate_sarif(malformed, scanner="Gitleaks", head_sha="head123")
    assert result["valid"] is False
    assert "invalid SARIF fingerprints" in result["errors"]


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


def test_artifact_without_run_attempt_uses_exact_trusted_run_attempt():
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
    assert result["valid"] is True


def test_artifact_without_run_attempt_is_rejected_without_trusted_run():
    metadata = {
        "id": 5,
        "name": "bandit.sarif",
        "expired": False,
        "workflow_run": {
            "id": 10,
            "repository": {"full_name": "stellababy2004/HelpChain"},
        },
    }
    result = validate_artifact_metadata(
        metadata,
        repository="stellababy2004/HelpChain",
        run_id=10,
        run_attempt=2,
        artifact_id=5,
        artifact_name="bandit.sarif",
    )
    assert result["valid"] is False
    assert "artifact run attempt metadata unavailable" in result["errors"]


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_artifact_download_http_errors_are_incomplete(monkeypatch, tmp_path, status):
    error = urllib.error.HTTPError(
        "https://api.github.com/repos/stellababy2004/HelpChain/actions/artifacts/5/zip",
        status,
        "artifact download failure",
        hdrs=None,
        fp=None,
    )

    class FailingOpener:
        def open(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(
        "scripts.security_release_gate_collect.urllib.request.build_opener",
        lambda *handlers: FailingOpener(),
    )
    with pytest.raises(
        GitHubApiError, match=rf"artifact download failed: HTTP {status}"
    ):
        GitHubClient("token", "stellababy2004/HelpChain").download_artifact(
            5, tmp_path / "artifact.zip"
        )


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


def test_invalid_zip_download_is_rejected(tmp_path):
    archive = tmp_path / "invalid.zip"
    archive.write_bytes(b"not-a-zip")
    with pytest.raises(zipfile.BadZipFile):
        safe_zip_members(archive)


def test_artifact_download_uses_github_json_accept_header(monkeypatch, tmp_path):
    import io
    import urllib.request

    from scripts.security_release_gate_collect import GitHubClient

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(b"PK\\x03\\x04test")

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeOpener:
        def open(self, request, timeout):
            captured["accept"] = request.get_header("Accept")
            return FakeResponse()

    def fake_build_opener(*handlers):
        return FakeOpener()

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)

    destination = tmp_path / "artifact.zip"
    GitHubClient("test-token", "owner/repo").download_artifact(123, destination)

    assert captured["accept"] == "application/vnd.github+json"
    assert destination.read_bytes() == b"PK\\x03\\x04test"
