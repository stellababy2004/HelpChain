from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping

APP_IMPORT_PATH = "backend.appy:app"
ROOT = Path(__file__).resolve().parents[1]

# Legacy write-guard constants kept for older scripts that still import them.
CANONICAL_DB_URI = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
CANONICAL_DB_PATH = r"C:\dev\HelpChain.bg\backend\instance\app_clean.db"

PRIMARY_LOCAL_DB_PATH = ROOT / "instance" / "hc_local_dev.db"
FALLBACK_LOCAL_DB_PATH = ROOT / "backend" / "instance" / "app_clean.db"
PRIMARY_LOCAL_DB_URI = f"sqlite:///{PRIMARY_LOCAL_DB_PATH.as_posix()}"
FALLBACK_LOCAL_DB_URI = f"sqlite:///{FALLBACK_LOCAL_DB_PATH.as_posix()}"

LOCAL_RUNTIME_REQUIRED_TABLES = ("admin_users", "structures", "users", "cases")
LOCAL_RUNTIME_REQUIRED_CASE_COLUMNS = ("latitude", "longitude", "status", "priority")

LEGACY_SQLITE_HINTS = (
    "instance/hc_local_dev.db",
    "instance/volunteers.db",
    "instance/app.db",
    "instance/hc_run.db",
)


@dataclass(frozen=True)
class RuntimeDbHealth:
    path: Path
    uri: str
    exists: bool
    healthy: bool
    missing_tables: tuple[str, ...]
    missing_case_columns: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class LocalRuntimeDbSelection:
    apply_contract: bool
    selected_path: Path | None
    selected_uri: str | None
    selected_label: str
    reason: str
    configured_uri: str | None
    configured_path: Path | None
    configured_source: str
    primary: RuntimeDbHealth
    fallback: RuntimeDbHealth

    @property
    def selected_health(self) -> RuntimeDbHealth | None:
        if self.selected_label == "primary":
            return self.primary
        if self.selected_label == "fallback":
            return self.fallback
        return None


def normalize_uri(uri: str | None) -> str:
    return str(uri or "").strip().replace("\\", "/")


def _sqlite_uri_for_path(path: Path) -> str:
    return f"sqlite:///{Path(path).resolve().as_posix()}"


def _read_env_file(root: Path = ROOT) -> dict[str, str]:
    env_path = root / ".env"
    if not env_path.exists():
        return {}

    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _merged_env(
    env: Mapping[str, str] | None = None, root: Path = ROOT
) -> dict[str, str]:
    merged = _read_env_file(root)
    source = os.environ if env is None else env
    merged.update({k: v for k, v in source.items() if v})
    return merged


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_testing_env(env: Mapping[str, str]) -> bool:
    if _truthy(env.get("HELPCHAIN_TESTING")):
        return True
    if env.get("PYTEST_CURRENT_TEST"):
        return True
    for key in ("HC_ENV", "APP_ENV", "FLASK_ENV", "FLASK_CONFIG"):
        if (env.get(key) or "").strip().lower() == "test":
            return True
    return False


def _resolve_configured_db_uri(
    env: Mapping[str, str] | None = None, root: Path = ROOT
) -> tuple[str, str]:
    merged = _merged_env(env, root)

    raw_path = (merged.get("HC_DB_PATH") or "").strip()
    if raw_path:
        path = Path(os.path.expandvars(raw_path))
        if not path.is_absolute():
            path = (root / path).resolve()
        return _sqlite_uri_for_path(path), "HC_DB_PATH"

    raw_url = (merged.get("DATABASE_URL") or "").strip()
    if raw_url:
        url = os.path.expandvars(raw_url)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if "://" not in url:
            return _sqlite_uri_for_path((root / url).resolve()), "DATABASE_URL"
        return normalize_uri(url), "DATABASE_URL"

    raw_sqlalchemy = (merged.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if raw_sqlalchemy:
        url = os.path.expandvars(raw_sqlalchemy)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if "://" not in url:
            return _sqlite_uri_for_path((root / url).resolve()), "SQLALCHEMY_DATABASE_URI"
        return normalize_uri(url), "SQLALCHEMY_DATABASE_URI"

    return PRIMARY_LOCAL_DB_URI, "default_primary"


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


def runtime_mismatch_error(actual_uri: str | None, expected_uri: str | None) -> str:
    return (
        "ERROR: Refusing to write to unexpected local runtime DB target.\n"
        "Expected:\n"
        f"{expected_uri}\n"
        "Actual:\n"
        f"{actual_uri}"
    )


def runtime_confirmation_error() -> str:
    return (
        "ERROR: Refusing DB write without explicit --confirm-canonical-db flag "
        "(effective local runtime DB)."
    )


def db_path_from_sqlite_uri(uri: str | None) -> Path | None:
    norm = normalize_uri(uri)
    if not norm.lower().startswith("sqlite:"):
        return None
    raw_path = norm.replace("sqlite:///", "", 1).replace("sqlite://", "", 1)
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def inspect_runtime_db(path: Path) -> RuntimeDbHealth:
    resolved = Path(path).resolve()
    exists = resolved.exists()
    if not exists:
        return RuntimeDbHealth(
            path=resolved,
            uri=_sqlite_uri_for_path(resolved),
            exists=False,
            healthy=False,
            missing_tables=tuple(LOCAL_RUNTIME_REQUIRED_TABLES),
            missing_case_columns=tuple(LOCAL_RUNTIME_REQUIRED_CASE_COLUMNS),
            error="database file missing",
        )

    try:
        con = sqlite3.connect(resolved)
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(
                table for table in LOCAL_RUNTIME_REQUIRED_TABLES if table not in tables
            )
            missing_case_columns: tuple[str, ...] = ()
            if "cases" in tables:
                case_columns = {
                    row[1] for row in con.execute("PRAGMA table_info(cases)").fetchall()
                }
                missing_case_columns = tuple(
                    col
                    for col in LOCAL_RUNTIME_REQUIRED_CASE_COLUMNS
                    if col not in case_columns
                )
            else:
                missing_case_columns = tuple(LOCAL_RUNTIME_REQUIRED_CASE_COLUMNS)
        finally:
            con.close()
    except Exception as exc:
        return RuntimeDbHealth(
            path=resolved,
            uri=_sqlite_uri_for_path(resolved),
            exists=True,
            healthy=False,
            missing_tables=tuple(LOCAL_RUNTIME_REQUIRED_TABLES),
            missing_case_columns=tuple(LOCAL_RUNTIME_REQUIRED_CASE_COLUMNS),
            error=str(exc),
        )

    healthy = not missing_tables and not missing_case_columns
    return RuntimeDbHealth(
        path=resolved,
        uri=_sqlite_uri_for_path(resolved),
        exists=True,
        healthy=healthy,
        missing_tables=missing_tables,
        missing_case_columns=missing_case_columns,
        error=None,
    )


def select_local_runtime_db(
    env: Mapping[str, str] | None = None,
    *,
    root: Path = ROOT,
    primary_path: Path | None = None,
    fallback_path: Path | None = None,
) -> LocalRuntimeDbSelection:
    merged = _merged_env(env, root)
    configured_uri, configured_source = _resolve_configured_db_uri(merged, root)
    configured_path = db_path_from_sqlite_uri(configured_uri)

    primary = inspect_runtime_db(primary_path or PRIMARY_LOCAL_DB_PATH)
    fallback = inspect_runtime_db(fallback_path or FALLBACK_LOCAL_DB_PATH)

    if _is_testing_env(merged):
        return LocalRuntimeDbSelection(
            apply_contract=False,
            selected_path=configured_path,
            selected_uri=configured_uri,
            selected_label="configured",
            reason="test environment; local runtime DB contract not applied",
            configured_uri=configured_uri,
            configured_path=configured_path,
            configured_source=configured_source,
            primary=primary,
            fallback=fallback,
        )

    if configured_uri and not normalize_uri(configured_uri).lower().startswith("sqlite:"):
        return LocalRuntimeDbSelection(
            apply_contract=False,
            selected_path=configured_path,
            selected_uri=configured_uri,
            selected_label="configured",
            reason="explicit non-sqlite runtime DB configured; local sqlite contract not applied",
            configured_uri=configured_uri,
            configured_path=configured_path,
            configured_source=configured_source,
            primary=primary,
            fallback=fallback,
        )

    if primary.healthy:
        return LocalRuntimeDbSelection(
            apply_contract=True,
            selected_path=primary.path,
            selected_uri=primary.uri,
            selected_label="primary",
            reason="primary local DB is healthy",
            configured_uri=configured_uri,
            configured_path=configured_path,
            configured_source=configured_source,
            primary=primary,
            fallback=fallback,
        )

    if fallback.healthy:
        return LocalRuntimeDbSelection(
            apply_contract=True,
            selected_path=fallback.path,
            selected_uri=fallback.uri,
            selected_label="fallback",
            reason="primary local DB is unhealthy; using healthy fallback DB",
            configured_uri=configured_uri,
            configured_path=configured_path,
            configured_source=configured_source,
            primary=primary,
            fallback=fallback,
        )

    return LocalRuntimeDbSelection(
        apply_contract=True,
        selected_path=primary.path,
        selected_uri=primary.uri,
        selected_label="primary",
        reason="no healthy local DB found; keeping the primary local DB as the repair target",
        configured_uri=configured_uri,
        configured_path=configured_path,
        configured_source=configured_source,
        primary=primary,
        fallback=fallback,
    )


def apply_local_runtime_db_contract(
    env: MutableMapping[str, str] | None = None,
    *,
    root: Path = ROOT,
    primary_path: Path | None = None,
    fallback_path: Path | None = None,
) -> LocalRuntimeDbSelection:
    selection = select_local_runtime_db(
        env=env,
        root=root,
        primary_path=primary_path,
        fallback_path=fallback_path,
    )
    if not selection.apply_contract or not selection.selected_path or not selection.selected_uri:
        return selection

    target_env = os.environ if env is None else env
    target_env["HC_DB_PATH"] = str(selection.selected_path)
    target_env["SQLALCHEMY_DATABASE_URI"] = selection.selected_uri
    target_env["DATABASE_URL"] = selection.selected_uri
    return selection
