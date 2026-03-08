from __future__ import annotations

from pathlib import Path

APP_IMPORT_PATH = "backend.appy:app"
CANONICAL_DB_URI = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
CANONICAL_DB_PATH = r"C:\dev\HelpChain.bg\backend\instance\app_clean.db"

LEGACY_SQLITE_HINTS = (
    "instance/hc_local_dev.db",
    "instance/volunteers.db",
    "instance/app.db",
    "instance/hc_run.db",
)


def normalize_uri(uri: str | None) -> str:
    return str(uri or "").strip().replace("\\", "/")


def is_canonical_db_uri(uri: str | None) -> bool:
    return normalize_uri(uri) == normalize_uri(CANONICAL_DB_URI)


def detect_legacy_sqlite_hint(uri: str | None) -> str | None:
    norm = normalize_uri(uri).lower()
    for hint in LEGACY_SQLITE_HINTS:
        if hint.lower() in norm:
            return hint
    return None


def print_app_db_preflight(actual_uri: str | None) -> None:
    print(f"APP: {APP_IMPORT_PATH}")
    print(f"DB: {actual_uri}")


def canonical_mismatch_error(actual_uri: str | None) -> str:
    return (
        "ERROR: Refusing to write to non-canonical DB target.\n"
        "Expected:\n"
        f"{CANONICAL_DB_URI}\n"
        "Actual:\n"
        f"{actual_uri}"
    )


def canonical_confirmation_error() -> str:
    return "ERROR: Refusing DB write without explicit --confirm-canonical-db flag."


def db_path_from_sqlite_uri(uri: str | None) -> Path | None:
    norm = normalize_uri(uri)
    prefix = "sqlite:///"
    if not norm.lower().startswith(prefix):
        return None
    raw_path = norm[len(prefix) :]
    if not raw_path:
        return None
    return Path(raw_path)
