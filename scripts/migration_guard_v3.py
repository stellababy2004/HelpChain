import sys
import re
from pathlib import Path
import subprocess

MIGRATIONS = Path("migrations/versions")

errors = []
warnings = []

graph = {}
revisions = {}
down_revisions = {}

DANGEROUS = [
    "batch_alter_table",
    "alter_column",
    "drop_column",
    "server_default",
]

REBUILD_TRIGGERS = [
    "batch_alter_table",
    "alter_column",
    "drop_constraint",
]


def parse_revision(file, content):
    rev = re.search(r"revision\s*=\s*['\"](.+?)['\"]", content)
    down = re.search(r"down_revision\s*=\s*['\"](.+?)['\"]", content)

    if rev:
        revisions[rev.group(1)] = file

    if rev and down:
        down_revisions[rev.group(1)] = down.group(1)


def detect_rebuild(file, content):
    for pattern in REBUILD_TRIGGERS:
        if pattern in content:
            warnings.append(f"{file}: SQLite rebuild risk -> {pattern}")


def detect_dangerous(file, content):
    for pattern in DANGEROUS:
        if pattern in content:
            errors.append(f"{file}: dangerous pattern -> {pattern}")


def detect_tmp(file, content):
    if "_alembic_tmp" in content:
        errors.append(f"{file}: uses _alembic_tmp table")


def detect_duplicates(file, content):
    indexes = re.findall(r'create_index\(\s*"([^"]+)"', content)
    for idx in indexes:
        if idx in seen_indexes:
            errors.append(f"Duplicate index {idx}")
        seen_indexes.add(idx)


def build_graph():
    for rev, down in down_revisions.items():
        graph.setdefault(down, []).append(rev)


def detect_heads():
    all_revs = set(revisions.keys())
    all_down = set(down_revisions.values())

    heads = list(all_revs - all_down)

    if len(heads) > 1:
        errors.append(f"Multiple heads detected: {heads}")

    return heads


def estimate_risk():

    score = 10

    if any("batch_alter_table" in e for e in errors + warnings):
        score -= 4

    if any("alter_column" in e for e in errors):
        score -= 2

    if any("Multiple heads" in e for e in errors):
        score -= 3

    if len(errors) > 5:
        score -= 2

    return max(score, 1)


def scan():

    for file in MIGRATIONS.glob("*.py"):
        content = file.read_text(encoding="utf-8")

        parse_revision(file, content)
        detect_rebuild(file, content)
        detect_dangerous(file, content)
        detect_tmp(file, content)
        detect_duplicates(file, content)


def main():

    global seen_indexes
    seen_indexes = set()

    if not MIGRATIONS.exists():
        print("No migrations directory")
        sys.exit(0)

    scan()
    build_graph()
    heads = detect_heads()

    score = estimate_risk()

    print("\nDATABASE MIGRATION AUDIT\n")

    print("Heads:", heads)
    print("\nGraph:")
    for k, v in graph.items():
        print(f"{k} -> {v}")

    print("\nWarnings:")
    for w in warnings:
        print(" -", w)

    print("\nErrors:")
    for e in errors:
        print(" -", e)

    print("\nProduction safety score:", score, "/10")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
