import re
import sys
from pathlib import Path

FORBIDDEN = [
    r"op\.drop_table",
    r"op\.drop_column",
    r"op\.alter_column",
    r"sa\.Column\(.*nullable=False",
    r"op\.execute\(\"DROP",
]

def scan_file(path: Path):
    text = path.read_text()

    for rule in FORBIDDEN:
        if re.search(rule, text):
            print(f"\n❌ Dangerous migration detected in {path.name}")
            print(f"Matched rule: {rule}")
            return False

    return True


def main():
    migrations = Path("migrations/versions")

    failed = False

    for file in migrations.glob("*.py"):
        if not scan_file(file):
            failed = True

    if failed:
        print("\n🚫 Migration blocked by linter")
        sys.exit(1)

    print("✔ Migration linter passed")


if __name__ == "__main__":
    main()
