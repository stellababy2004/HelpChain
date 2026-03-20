import re
from pathlib import Path

def analyze(file):

    text = file.read_text()

    issues = []

    if "batch_alter_table" in text:
        issues.append("⚠ Table rebuild detected")

    if "drop_index" in text:
        issues.append("⚠ Index drop detected")

    if "drop_table" in text:
        issues.append("🚨 Table drop detected")

    if "nullable=False" in text:
        issues.append("⚠ NOT NULL column")

    return issues


def main():

    migrations = Path("migrations/versions")

    for file in migrations.glob("*.py"):

        issues = analyze(file)

        if issues:
            print(f"\nMigration: {file.name}")

            for i in issues:
                print(i)


if __name__ == "__main__":
    main()
