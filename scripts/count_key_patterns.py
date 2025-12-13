import json
import re

PATH = "artifacts/high_confidence.json"

patterns = {
    "jwt": re.compile(r"^eyJ[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+$"),
    "github_pat": re.compile(r"^ghp_[0-9A-Za-z]{36}$"),
    "openai_key": re.compile(r"^sk-[A-Za-z0-9]{32,}$"),
    "aws_access_key": re.compile(r"^AKIA[0-9A-Z]{16}$"),
    "gcp_api_key": re.compile(r"^AIza[0-9A-Za-z_\-]{35}$"),
}


def main():
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    counts = {k: 0 for k in patterns}
    total = 0

    for item in data.get("findings", []):
        val = item.get("value", "")
        total += 1
        for name, pat in patterns.items():
            if pat.search(val):
                counts[name] += 1

    print("total_entries:", total)
    for k, v in counts.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
