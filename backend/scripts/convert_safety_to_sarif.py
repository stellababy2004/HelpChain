"""Convert safety JSON output to a minimal SARIF file.
Usage:
  python scripts/convert_safety_to_sarif.py safety.json safety.sarif
If safety JSON fails to parse, creates empty SARIF skeleton.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from typing import Any

SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"


def to_rule(issue):
    pkg = issue.get("package_name")
    vuln_id = issue.get("vulnerability_id") or issue.get("cve") or issue.get("id")
    name = f"{pkg}:{vuln_id}" if vuln_id else pkg
    return {
        "id": name,
        "name": name,
        "shortDescription": {"text": issue.get("advisory", "Vulnerability")[:120]},
        "fullDescription": {"text": issue.get("advisory", "")},
        "help": {
            "text": issue.get("advisory", ""),
            "markdown": issue.get("advisory", ""),
        },
        "properties": {
            "severity": issue.get("severity"),
            "cvss": issue.get("cvss"),
        },
    }


def to_result(issue):
    pkg = issue.get("package_name")
    vuln_id = issue.get("vulnerability_id") or issue.get("cve") or issue.get("id")
    msg = issue.get("advisory", "")
    fingerprint = hashlib.sha256(f"{pkg}:{vuln_id}:{msg}".encode()).hexdigest()
    return {
        "ruleId": f"{pkg}:{vuln_id}" if vuln_id else pkg,
        "ruleIndex": 0,  # will be adjusted later
        "level": level_map(issue.get("severity")),
        "message": {"text": msg},
        "fingerprints": {"issueHash": fingerprint},
        "properties": {
            "package": pkg,
            "installed_version": issue.get("installed_version"),
            "severity": issue.get("severity"),
        },
    }


def level_map(sev):
    sev = (sev or "").lower()
    if sev in {"critical", "high"}:
        return "error"
    if sev in {"medium"}:
        return "warning"
    if sev in {"low"}:
        return "note"
    return "none"


def _extract_json(raw: str) -> dict[str, Any]:
    # Try direct parse first
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    snippet = raw[start : end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return {}


def main(inp, outp):
    try:
        raw = open(inp, encoding="utf-8").read()
    except Exception:
        raw = "{}"
    data = _extract_json(raw)
    issues = []
    if isinstance(data, dict):
        if isinstance(data.get("issues"), list):
            issues = data["issues"]
        elif isinstance(data.get("vulnerabilities"), list):
            issues = data["vulnerabilities"]

    rules = []
    results = []
    for issue in issues:
        rule_obj = to_rule(issue)
        # Ensure unique rule ids
        if not any(r["id"] == rule_obj["id"] for r in rules):
            rules.append(rule_obj)
        results.append(to_result(issue))

    # map ruleIndex
    id_to_index = {r["id"]: i for i, r in enumerate(rules)}
    for res in results:
        rid = res.get("ruleId")
        res["ruleIndex"] = id_to_index.get(rid, 0)

    safety_version = None
    if isinstance(data, dict):
        safety_version = data.get("meta", {}).get("safety_version") or data.get(
            "report_meta", {}
        ).get("safety_version")

    sarif = {
        "version": "2.1.0",
        "$schema": SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "safety",
                        "informationUri": "https://pypi.org/project/safety/",
                        "rules": rules,
                        "version": safety_version,
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.datetime.utcnow().isoformat() + "Z",
                    }
                ],
                "results": results,
            }
        ],
    }
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(sarif, f, indent=2)
    print(f"[convert] Wrote SARIF with {len(results)} results to {outp}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_safety_to_sarif.py <input_json> <output_sarif>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
