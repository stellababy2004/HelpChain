#!/usr/bin/env python3
"""Parse SARIF/JSON artifacts and group secret findings.

Writes results to artifacts/analysis.json and prints a short summary.
"""
import json
import re
from pathlib import Path

SARIF_DIR = Path("artifacts/sarifs")
OUT = Path("artifacts/analysis.json")

JWT_RE = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
KEY_RE = re.compile(
    r"\b(?:sk_|pk_|ghp_|GITHUB_TOKEN|VERCEL|AIza[0-9A-Za-z-_]{35,}|AKIA[0-9A-Z]{16,})[A-Za-z0-9_\-\.]{8,}\b"
)
LONG_B64 = re.compile(r"[A-Za-z0-9_\-]{20,}")


def extract_candidates(text):
    if not text:
        return []
    cands = set()
    for r in (JWT_RE, KEY_RE):
        for m in r.findall(text):
            cands.add(m)
    # fallback: long base64-like tokens
    for m in LONG_B64.findall(text):
        if len(m) >= 40:
            cands.add(m)
    return list(cands)


def parse_file(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
    findings = []
    runs = data.get("runs") or []
    for run in runs:
        results = run.get("results") or []
        for res in results:
            message = res.get("message", {})
            text = message.get("text") or message.get("markdown") or ""
            rule = (
                res.get("ruleId")
                or res.get("ruleIndex")
                or res.get("rule", {}).get("id")
            )
            locations = []
            for loc in res.get("locations") or []:
                pl = loc.get("physicalLocation") or {}
                art = pl.get("artifactLocation") or {}
                uri = art.get("uri")
                region = pl.get("region") or {}
                if uri:
                    locations.append(
                        {
                            "uri": uri,
                            "startLine": region.get("startLine"),
                            "startColumn": region.get("startColumn"),
                        }
                    )
            # try properties matched string
            props = res.get("properties") or {}
            prop_match = props.get("matched") or props.get("secret") or None
            cands = set(extract_candidates(text))
            if prop_match:
                cands.add(prop_match)
            if not cands:
                # include message as low-confidence candidate
                if text.strip():
                    cands.add(text.strip())
            for c in cands:
                findings.append(
                    {
                        "value": c,
                        "rule": rule,
                        "message": text,
                        "locations": locations,
                        "source_file": str(p.name),
                    }
                )
    return findings


def main():
    all_findings = []
    for p in sorted(SARIF_DIR.glob("*")):
        if p.is_file() and p.suffix in (".json", ".sarif"):
            try:
                all_findings.extend(parse_file(p))
            except Exception as e:
                print(f"Failed to parse {p}: {e}")

    # group by value
    grouped = {}
    for f in all_findings:
        v = f["value"]
        entry = grouped.setdefault(
            v,
            {
                "value": v,
                "count": 0,
                "rules": set(),
                "messages": set(),
                "files": set(),
                "locations": [],
            },
        )
        entry["count"] += 1
        if f.get("rule"):
            entry["rules"].add(str(f["rule"]))
        if f.get("message"):
            entry["messages"].add(f["message"])
        for loc in f.get("locations", []):
            entry["locations"].append(loc)
            if loc.get("uri"):
                entry["files"].add(loc.get("uri"))
        entry["files"] = set(entry["files"])

    # normalize sets
    out = []
    for v, e in grouped.items():
        out.append(
            {
                "value": v,
                "count": e["count"],
                "rules": sorted(list(e["rules"])),
                "files": sorted(list(e["files"])),
                "example_locations": e["locations"][:5],
                "example_messages": list(e["messages"])[:3],
                "suggested_action": "review-and-revoke",
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "summary_count": len(out),
                "findings": sorted(out, key=lambda x: -x["count"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Parsed {len(all_findings)} findings, grouped to {len(out)} unique values. Written to {OUT}"
    )


if __name__ == "__main__":
    main()
