import json
import re
from pathlib import Path

F = Path("artifacts/file_scan_analysis.json")
OUT = Path("artifacts/secret_scan_results.json")

patterns = {
    "jwt": re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),
    "openai": re.compile(r"sk-[A-Za-z0-9]{32,}"),
    "github_pat": re.compile(r"ghp_[0-9A-Za-z]{36}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "gcp_api_key": re.compile(r"AIZA[0-9A-Za-z_\-]{30,}|AIza[0-9A-Za-z_\-]{20,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |)PRIVATE KEY-----"),
}


def main():
    if not F.exists():
        print(f"{F} not found")
        return
    text = F.read_text(encoding="utf-8", errors="ignore")
    results = {}
    for name, pat in patterns.items():
        found = set(pat.findall(text))
        results[name] = {"count": len(found), "examples": list(found)[:5]}

    # also check for long base64-ish strings (>80 chars)
    long_b64 = set(re.findall(r"[A-Za-z0-9_\-]{80,}", text))
    results["long_base64_like"] = {
        "count": len(long_b64),
        "examples": list(long_b64)[:5],
    }

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
