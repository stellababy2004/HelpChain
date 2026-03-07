import re
import csv
import json
from pathlib import Path

TEMPLATE_DIR = Path("templates")
CSV_REPORT = Path("reports/i18n_heatmap.csv")
JSON_REPORT = Path("reports/i18n_heatmap.json")

key_pattern = re.compile(r"""\b_\s*\(\s*(?P<q>["'])(?P<key>[^"']+)(?P=q)\s*\)""")
visible_node_pattern = re.compile(r">([^<>]+)<")
script_style_pattern = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
jinja_expr_pattern = re.compile(r"{{.*?}}|{%-?.*?-%}|{%.*?%}", re.DOTALL)
punct_only_pattern = re.compile(r"^[\W_]+$", re.UNICODE)


def _is_visible_literal(text: str) -> bool:
    s = " ".join(text.split()).strip()
    if len(s) < 2:
        return False
    if punct_only_pattern.fullmatch(s):
        return False
    return True


def score_bucket(score):
    if score > 80:
        return "GREEN"
    if score > 50:
        return "YELLOW"
    return "RED"


def analyze_file(file):
    text = file.read_text(errors="ignore")
    text = script_style_pattern.sub("", text)

    wrapped_segments = 0
    visible_segments = 0

    for node in visible_node_pattern.findall(text):
        wrapped_in_node = len(list(key_pattern.finditer(node)))
        if wrapped_in_node:
            wrapped_segments += wrapped_in_node
            visible_segments += wrapped_in_node

        literal_part = jinja_expr_pattern.sub(" ", node)
        if _is_visible_literal(literal_part):
            visible_segments += 1

    if visible_segments == 0:
        return 100

    score = int((wrapped_segments / visible_segments) * 100)
    return score


def main():
    results: list[dict[str, object]] = []

    for file in TEMPLATE_DIR.rglob("*.html"):
        score = analyze_file(file)
        rel_path = file.relative_to(TEMPLATE_DIR).as_posix()
        bucket = score_bucket(score)
        results.append({"file": rel_path, "score": score, "bucket": bucket})

    results.sort(key=lambda x: (x["score"], x["file"]))

    red_count = sum(1 for r in results if r["bucket"] == "RED")
    yellow_count = sum(1 for r in results if r["bucket"] == "YELLOW")
    green_count = sum(1 for r in results if r["bucket"] == "GREEN")

    CSV_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "score", "bucket"])
        writer.writeheader()
        writer.writerows(results)

    JSON_REPORT.parent.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\nTranslation Heatmap\n")
    for row in results:
        print(f"{row['file']:45} {row['bucket']:6} {row['score']}%")

    print("\nSummary")
    print(f"total templates: {len(results)}")
    print(f"RED count: {red_count}")
    print(f"YELLOW count: {yellow_count}")
    print(f"GREEN count: {green_count}")
    print(f"CSV report: {CSV_REPORT.as_posix()}")
    print(f"JSON report: {JSON_REPORT.as_posix()}")


if __name__ == "__main__":
    main()
