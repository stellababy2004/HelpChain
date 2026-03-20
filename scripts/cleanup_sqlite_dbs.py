from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.appy import app

BACKUP_DIR = PROJECT_ROOT / "backups"
DRY_RUN = True


def sqlite_uri_to_path(uri: str) -> Path | None:
    if not uri or not uri.startswith("sqlite:///"):
        return None
    raw = uri.replace("sqlite:///", "", 1)
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path.resolve()


def list_db_files() -> list[Path]:
    db_files: list[Path] = []
    for root, _dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        if "backups" in root_path.parts:
            continue
        for file in files:
            if file.endswith(".db"):
                db_files.append((root_path / file).resolve())
    return sorted(db_files)


def backup_file(path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    relative_name = path.relative_to(PROJECT_ROOT).as_posix().replace("/", "__")
    backup_path = BACKUP_DIR / f"{relative_name}.bak.db"
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> int:
    with app.app_context():
        active_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print("ACTIVE DB:", active_uri)

        active_path = sqlite_uri_to_path(active_uri)
        if active_path is None:
            print("No active SQLite database configured.")
            return 1

        print("DB FILES:")
        db_files = list_db_files()
        for path in db_files:
            print(path)

        for path in db_files:
            if path == active_path:
                print(f"SKIPPED (active DB): {path}")
                continue
            if path.name == "hc_local_dev.db":
                print(f"SKIPPED (by name safeguard): {path}")
                continue
            if not path.exists():
                continue

            backup_path = backup_file(path)
            print(f"BACKED UP: {path} -> {backup_path}")

            if DRY_RUN:
                print(f"[DRY-RUN] Would remove: {path}")
            else:
                path.unlink()
                print(f"REMOVED: {path}")

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
