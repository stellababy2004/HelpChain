"""Evaluate the non-destructive security release gate report."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "unclassified")
BLOCKING_SEVERITIES = {"critical", "high", "error"}
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_DISPOSITIONS_PATH = Path(
    "docs/security/PR-203-FINDINGS-DISPOSITIONS-2026-11-11.json"
)
EXPECTED_DISPOSITION_KEYS = {
    "bandit|b104|backend/helpchain_backend/src/extensions.py|23",
    "bandit|b104|backend/helpchain_backend/src/routes/admin.py|2148",
    "gitleaks|secret-key-assignment|tests/test_sensitive_logging_remediation.py|140",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_finding_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = posixpath.normpath(value.replace("\\", "/"))
    if (
        normalized in {".", ".."}
        or normalized.startswith("../")
        or normalized.startswith("/")
        or (len(normalized) > 1 and normalized[1] == ":")
    ):
        return None
    return normalized


def finding_key(finding: dict[str, Any]) -> str | None:
    scanner = finding.get("scanner")
    rule = finding.get("rule")
    path = normalize_finding_path(finding.get("path"))
    line = finding.get("line")
    package = finding.get("package")
    if (
        not isinstance(scanner, str)
        or not isinstance(rule, str)
        or (path is None and not (scanner.lower() == "pip-audit" and package))
    ):
        return None
    if path is None:
        return f"{scanner.lower()}|{rule.lower()}|package:{str(package).lower()}"
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        return None
    return f"{scanner.lower()}|{rule.lower()}|{path}|{line}"


def finding_identity_key(finding: dict[str, Any]) -> str | None:
    key = finding_key(finding)
    if key is None:
        return None
    fingerprint = finding.get("evidence_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return f"{key}|{fingerprint}"
    return key


def finding_context_digest(finding: dict[str, Any]) -> str | None:
    """Return a stable digest of trustworthy scanner/source context."""
    key = finding_key(finding)
    if key is None:
        return None
    scanner = str(finding["scanner"]).lower()
    path = normalize_finding_path(finding["path"])
    line = finding["line"]
    context: dict[str, Any] = {"finding_key": key}
    if scanner == "gitleaks":
        historical_commit = finding.get("historical_commit")
        if not isinstance(historical_commit, str) or not SHA1_PATTERN.fullmatch(
            historical_commit.lower()
        ):
            return None
        context["historical_commit"] = historical_commit.lower()
        context["scanner_identity"] = finding.get("identity")
        evidence_fingerprint = finding.get("evidence_fingerprint")
        if evidence_fingerprint is not None:
            if not isinstance(
                evidence_fingerprint, str
            ) or not SHA256_PATTERN.fullmatch(evidence_fingerprint):
                return None
            context["evidence_fingerprint"] = evidence_fingerprint
    else:
        try:
            source_lines = Path(path).read_text(encoding="utf-8").splitlines()
            context["source_line"] = source_lines[line - 1]
        except (OSError, UnicodeError, IndexError):
            return None
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_dispositions(
    document: Any,
    *,
    repository: str,
    today: date | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return {}, ["disposition document must be an object"]
    if document.get("schema_version") != 1:
        errors.append("unsupported disposition schema_version")
    if document.get("repository") != repository:
        errors.append("disposition repository mismatch")
    if document.get("approval_model") != "solo_owner_review":
        errors.append("unsupported disposition approval model")
    if document.get("independent_review") is not False:
        errors.append("independent review must be explicitly false")

    owner = document.get("owner")
    if not isinstance(owner, dict):
        errors.append("owner identity is required")
    else:
        if owner.get("login") != "stellababy2004":
            errors.append("owner identity mismatch")
        if not isinstance(owner.get("name"), str) or not owner.get("name"):
            errors.append("owner name is required")
        try:
            datetime.fromisoformat(str(owner.get("decision_date")))
        except ValueError:
            errors.append("invalid owner decision_date")

    entries = document.get("dispositions")
    if not isinstance(entries, list) or not entries:
        return {}, errors + ["dispositions must be a non-empty list"]

    dispositions: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("invalid disposition entry")
            continue
        key = finding_key(entry)
        if key is None or entry.get("finding_id") != key:
            errors.append("disposition finding identity mismatch")
            continue
        # New findings may be reviewed explicitly, but never auto-approved.
        # Exact identity, source-context digest, severity, expiry, and evidence
        # checks below remain mandatory for every additional disposition.
        if key not in EXPECTED_DISPOSITION_KEYS and entry.get("disposition") != "FALSE_POSITIVE":
            errors.append("new finding requires explicit false-positive review")
            continue
        if key in dispositions:
            errors.append("duplicate disposition finding identity")
            continue
        if entry.get("disposition") not in {
            "FALSE_POSITIVE",
            "OWNER_REVIEWED_HISTORICAL_TEST_FIXTURE",
        }:
            errors.append("unsupported disposition decision")
            continue
        if entry.get("expected_severity") != "unclassified":
            errors.append("disposition severity must remain unclassified")
            continue
        if not isinstance(
            entry.get("context_digest"), str
        ) or not SHA256_PATTERN.fullmatch(entry["context_digest"]):
            errors.append("valid context_digest is required")
            continue
        if not isinstance(entry.get("rationale"), str) or not entry.get("rationale"):
            errors.append("disposition rationale is required")
            continue
        if not isinstance(entry.get("evidence_ref"), str) or not entry.get(
            "evidence_ref"
        ):
            errors.append("disposition evidence_ref is required")
            continue
        try:
            expires_on = date.fromisoformat(str(entry.get("expires_on")))
        except ValueError:
            errors.append("invalid disposition expires_on")
            continue
        if expires_on <= (today or date.today()):
            errors.append("disposition is expired")
            continue
        if key.startswith("gitleaks|"):
            if entry.get("historical_commit") != (
                "07fa68d170c91db30392b5322e756dbf09ef6529"
            ):
                errors.append("historical Gitleaks commit mismatch")
                continue
        elif entry.get("historical_commit") is not None:
            errors.append("non-historical disposition has historical commit")
            continue
        dispositions[key] = entry

    if not EXPECTED_DISPOSITION_KEYS.issubset(dispositions):
        errors.append("disposition document does not cover the reviewed findings")
    return dispositions, errors


def apply_dispositions(
    findings: list[dict[str, Any]],
    document: Any,
    *,
    repository: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    dispositions, errors = (
        validate_dispositions(document, repository=repository)
        if document is not None
        else ({}, ["disposition document is missing"])
    )
    recognized: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        key = finding_key(finding)
        identity_key = finding_identity_key(finding)
        entry = dispositions.get(key) if key else None
        severity = str(finding.get("severity", "unclassified")).lower()
        if key is None:
            unresolved.append(
                {"finding_id": None, "reason": "unstable finding identity"}
            )
        elif identity_key in seen:
            unresolved.append(
                {"finding_id": key, "reason": "ambiguous duplicate finding"}
            )
        else:
            seen.add(identity_key)
            if entry is None:
                unresolved.append({"finding_id": key, "reason": "no exact disposition"})
            elif severity in BLOCKING_SEVERITIES:
                unresolved.append(
                    {
                        "finding_id": key,
                        "reason": "blocking severity cannot be dispositioned",
                    }
                )
            else:
                context_digest = finding_context_digest(finding)
                if context_digest is None:
                    unresolved.append(
                        {
                            "finding_id": key,
                            "reason": "trustworthy finding context unavailable",
                        }
                    )
                elif context_digest != entry.get("context_digest"):
                    unresolved.append(
                        {"finding_id": key, "reason": "finding context changed"}
                    )
                elif key.startswith("gitleaks|") and (
                    finding.get("historical_commit") != entry.get("historical_commit")
                    or finding.get("identity") != entry.get("identity")
                ):
                    unresolved.append(
                        {"finding_id": key, "reason": "historical evidence mismatch"}
                    )
                elif severity != entry.get("expected_severity"):
                    unresolved.append(
                        {"finding_id": key, "reason": "finding severity changed"}
                    )
                else:
                    recognized.append(
                        {
                            "finding_id": key,
                            "disposition": entry["disposition"],
                            "evidence_ref": entry["evidence_ref"],
                        }
                    )
    identity_keys = [finding_identity_key(item) for item in findings]
    if None in identity_keys or len(findings) != len(set(identity_keys)):
        errors.append("scanner finding identities are ambiguous")
    return recognized, unresolved, errors


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


def scanner_evidence_is_complete(item: dict[str, Any], head_sha: str) -> bool:
    common = (
        item.get("status") == "success"
        and item.get("report_present") is True
        and item.get("report_valid") is True
    )
    evidence_class = item.get("evidence_class")
    if evidence_class == "local_dependency_check":
        return (
            common
            and item.get("name") == "pip-audit api/requirements.txt"
            and item.get("run_id") is None
            and item.get("run_attempt") is None
            and item.get("head_sha") is None
            and item.get("event") is None
        )
    if evidence_class == "code_scanning_api":
        return (
            common
            and item.get("name") == "github-code-scanning-api"
            and item.get("run_id") == f"code-scanning-api:{head_sha}"
            and item.get("run_attempt") is None
            and item.get("head_sha") == head_sha
            and item.get("event") == "pull_request"
        )
    if evidence_class not in {None, "workflow_artifact"}:
        return False
    return (
        common
        and item.get("run_id") is not None
        and item.get("run_attempt") is not None
        and item.get("head_sha") == head_sha
        and item.get("event") in {"pull_request", "workflow_dispatch"}
    )


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
    dispositions: Any = None,
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
        and all(scanner_evidence_is_complete(item, head_sha) for item in scanner_status)
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
    recognized_dispositions, unresolved_dispositions, disposition_errors = (
        apply_dispositions(
            scanner_findings,
            dispositions,
            repository=repository,
        )
    )
    if dependency_findings != len(scanner_findings):
        disposition_errors.append(
            "scanner finding count does not match evidence counts"
        )
    if not scanner_complete:
        status = "INCOMPLETE"
    elif new_high or blocking_scanner_findings:
        status = "FAIL"
    elif new_alerts and reachability == "unknown":
        status = "REVIEW REQUIRED"
    elif (dependency_findings or scanner_findings) and (
        unresolved_dispositions
        or disposition_errors
        or len(recognized_dispositions) != len(scanner_findings)
    ):
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
        "recognized_disposition_count": len(recognized_dispositions),
        "dispositioned_findings": recognized_dispositions,
        "unresolved_dispositions": unresolved_dispositions,
        "disposition_errors": disposition_errors,
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
    parser.add_argument("--dispositions", type=Path, default=DEFAULT_DISPOSITIONS_PATH)
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
        dispositions = (
            load_json(args.dispositions) if args.dispositions.exists() else None
        )
        report = evaluate(
            baseline,
            alerts,
            api_ok=args.api_ok,
            scanner_status=scanner_status,
            repository=args.repository,
            head_sha=args.head_sha,
            base_sha=args.base_sha,
            scanner_findings=scanner_findings,
            dispositions=dispositions,
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
