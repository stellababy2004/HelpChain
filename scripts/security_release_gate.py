"""Evaluate the non-destructive security release gate report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "unclassified")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def classify_alert(alert: dict[str, Any]) -> str:
    severity = str(
        alert.get("rule", {}).get("security_severity_level")
        or alert.get("severity")
        or "unclassified"
    ).lower()
    return severity if severity in SEVERITIES[:-1] else "unclassified"


def alert_signature(alert: dict[str, Any]) -> str:
    instance = alert.get("most_recent_instance", {})
    location = instance.get("location", {})
    path = location.get("path", "")
    line = location.get("start_line", "")
    rule = alert.get("rule", {}).get("id", "")
    tool = alert.get("tool", {}).get("name", "")
    commit_sha = alert.get("most_recent_instance", {}).get("commit_sha", "")
    severity = alert.get("rule", {}).get("security_severity_level", "")
    state = alert.get("state", "")
    return f"{tool}|{rule}|{path}|{line}|{commit_sha}|{severity}|{state}"


def validate_baseline(baseline: dict[str, Any], repository: str) -> list[str]:
    errors = []
    if baseline.get("schemaVersion") != 1:
        errors.append("unsupported schemaVersion")
    if baseline.get("repository") != repository:
        errors.append("baseline repository mismatch")
    if baseline.get("source") != "github-code-scanning-api":
        errors.append("untrusted baseline source")
    captured_at = baseline.get("capturedAt")
    try:
        datetime.fromisoformat(str(captured_at))
    except ValueError:
        errors.append("invalid capturedAt")
    ids = baseline.get("alert_numbers")
    if (
        not isinstance(ids, list)
        or not ids
        or not all(isinstance(item, int) for item in ids)
    ):
        errors.append("alert_numbers must be a non-empty integer list")
    elif len(ids) != len(set(ids)):
        errors.append("duplicate alert IDs")
    records = baseline.get("alert_records")
    if not isinstance(records, list) or len(records) != len(ids or []):
        errors.append("alert_records must cover every alert ID")
    elif len({record.get("number") for record in records}) != len(records):
        errors.append("duplicate alert records")
    return errors


def evaluate(
    baseline: dict[str, Any],
    alerts: list[dict[str, Any]],
    *,
    api_ok: bool,
    scanner_status: list[dict[str, Any]] | None = None,
    repository: str = "stellababy2004/HelpChain",
    head_sha: str | None = None,
    base_sha: str | None = None,
    scanner_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    baseline_errors = validate_baseline(baseline, repository)
    baseline_numbers = {int(number) for number in baseline.get("alert_numbers", [])}
    baseline_signatures = {
        record.get("signature")
        for record in baseline.get("alert_records", [])
        if isinstance(record, dict)
    }
    commit_errors = []
    if not head_sha or not base_sha:
        commit_errors.append("head_sha and base_sha are required")
    elif any(
        alert.get("most_recent_instance", {}).get("commit_sha") != head_sha
        for alert in alerts
    ):
        commit_errors.append("finding is not associated with PR head SHA")
    new_alerts = [
        alert
        for alert in alerts
        if int(alert.get("number", -1)) not in baseline_numbers
        or alert_signature(alert) not in baseline_signatures
    ]
    counts = Counter(classify_alert(alert) for alert in alerts)
    new_high = [
        alert for alert in new_alerts if classify_alert(alert) in {"critical", "high"}
    ]
    scanner_status = scanner_status or [
        {
            "name": "github-code-scanning-api",
            "status": "success",
            "report_present": api_ok,
        }
    ]
    scanner_findings = scanner_findings or []
    scanner_complete = bool(
        api_ok
        and not baseline_errors
        and not commit_errors
        and all(
            item.get("status") == "success"
            and item.get("report_present") is True
            and item.get("report_valid") is True
            and item.get("run_id") is not None
            and item.get("head_sha") == head_sha
            and item.get("event") in {"pull_request", "workflow_dispatch"}
            for item in scanner_status
        )
    )
    dependency_findings = sum(
        int(item.get("findings_count", 0) or 0) for item in scanner_status
    )
    reachability = "unknown"
    blocking_scanner_findings = [
        finding
        for finding in scanner_findings
        if str(finding.get("severity", "")).lower() in {"critical", "high", "error"}
    ]
    if not scanner_complete:
        status = "INCOMPLETE"
    elif new_high or blocking_scanner_findings:
        status = "FAIL"
    elif new_alerts and reachability == "unknown":
        status = "REVIEW REQUIRED"
    elif dependency_findings:
        status = "REVIEW REQUIRED"
    else:
        status = "PASS"
    return {
        "status": status,
        "scanner_complete": scanner_complete,
        "baseline_valid": isinstance(baseline.get("alert_numbers"), list),
        "baseline_errors": baseline_errors,
        "commit_errors": commit_errors,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "existing_alert_count": len(alerts),
        "new_alert_count": len(new_alerts),
        "new_critical_high_count": len(new_high),
        "dependency_findings": dependency_findings,
        "scanner_findings": scanner_findings,
        "blocking_scanner_finding_count": len(blocking_scanner_findings),
        "reachability": "unknown",
        "scanner_status": scanner_status,
        "severity_counts": {
            severity: counts.get(severity, 0) for severity in SEVERITIES
        },
        "new_alerts": [
            {
                "number": alert.get("number"),
                "tool": alert.get("tool", {}).get("name"),
                "rule": alert.get("rule", {}).get("id"),
                "severity": classify_alert(alert),
                "path": alert.get("most_recent_instance", {})
                .get("location", {})
                .get("path"),
            }
            for alert in new_alerts
        ],
        "decision": (
            "Reporting mode: no merge blocking is enabled. New confirmed production Critical/High findings require owner triage."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--alerts", type=Path, required=True)
    parser.add_argument("--api-ok", action="store_true")
    parser.add_argument("--scan-status", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scanner-findings", type=Path)
    args = parser.parse_args()

    try:
        baseline = load_json(args.baseline)
        alerts = load_json(args.alerts)
        if not isinstance(baseline, dict) or not isinstance(alerts, list):
            raise ValueError("baseline or alert payload has an invalid shape")
        scanner_status = load_json(args.scan_status) if args.scan_status else None
        if scanner_status is not None and not isinstance(scanner_status, list):
            raise ValueError("scanner status payload has an invalid shape")
        scanner_findings = (
            load_json(args.scanner_findings) if args.scanner_findings else []
        )
        if not isinstance(scanner_findings, list):
            raise ValueError("scanner findings payload has an invalid shape")
        report = evaluate(
            baseline,
            alerts,
            api_ok=args.api_ok,
            scanner_status=scanner_status,
            repository=args.repository,
            head_sha=args.head_sha,
            base_sha=args.base_sha,
            scanner_findings=scanner_findings,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"status": "INCOMPLETE", "error": str(exc)}

    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
