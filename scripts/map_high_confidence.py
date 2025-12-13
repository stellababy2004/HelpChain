import json
import re
from collections import Counter

PATH = "artifacts/high_confidence.json"
OUT = "artifacts/high_confidence_summary.json"

jwt_re = re.compile(r"^eyJ[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+$")
aws_re = re.compile(r"^AKIA[0-9A-Z]{16}$")
gh_re = re.compile(r"^ghp_[0-9A-Za-z]{36}$")
openai_re = re.compile(r"^sk-[A-Za-z0-9]{32,}$")
gcp_re = re.compile(r"^AIza[0-9A-Za-z_\-]{35}$")
slack_re = re.compile(r"^xox[baprs]-")


def categorize(val):
    if jwt_re.search(val):
        return "jwt"
    if aws_re.search(val):
        return "aws_access_key"
    if gh_re.search(val):
        return "github_pat"
    if openai_re.search(val):
        return "openai_key"
    if gcp_re.search(val):
        return "gcp_api_key"
    if slack_re.search(val):
        return "slack_token"
    if "-----BEGIN PRIVATE KEY-----" in val or "BEGIN RSA PRIVATE KEY" in val:
        return "private_key"
    if len(val) > 80:
        return "long_base64_or_cert"
    if re.match(r"^[0-9A-Za-z\-_]{20,}$", val):
        return "generic_token"
    return "other"


def main():
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    total = data.get("count", len(data.get("findings", [])))
    cats = Counter()
    top = []

    for item in data.get("findings", []):
        val = item.get("value", "")
        cnt = item.get("count", 1)
        cat = categorize(val)
        cats[cat] += cnt
        top.append((cnt, val))

    top.sort(reverse=True)
    summary = {
        "total_candidates": total,
        "category_counts": dict(cats),
        "top_20": [{"count": c, "value": v} for c, v in top[:20]],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
