from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

from backend.local_db_guard import select_local_runtime_db


def _create_runtime_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE admin_users (id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE structures (id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        con.execute(
            """
            CREATE TABLE cases (
                id INTEGER PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                status TEXT,
                priority TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _workspace_tmp_dir() -> Path:
    path = Path(".tmp") / f"local_db_guard_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_select_local_runtime_db_prefers_healthy_primary():
    tmp_path = _workspace_tmp_dir()
    try:
        primary = tmp_path / "hc_local_dev.db"
        fallback = tmp_path / "app_clean.db"
        _create_runtime_db(primary)
        _create_runtime_db(fallback)

        selection = select_local_runtime_db(
            env={},
            root=tmp_path,
            primary_path=primary,
            fallback_path=fallback,
        )

        assert selection.apply_contract is True
        assert selection.selected_label == "primary"
        assert selection.selected_path == primary.resolve()
        assert selection.selected_health is not None
        assert selection.selected_health.healthy is True
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_select_local_runtime_db_uses_fallback_when_primary_is_unhealthy():
    tmp_path = _workspace_tmp_dir()
    try:
        primary = tmp_path / "hc_local_dev.db"
        fallback = tmp_path / "app_clean.db"
        primary.parent.mkdir(parents=True, exist_ok=True)
        primary.touch()
        _create_runtime_db(fallback)

        selection = select_local_runtime_db(
            env={},
            root=tmp_path,
            primary_path=primary,
            fallback_path=fallback,
        )

        assert selection.apply_contract is True
        assert selection.selected_label == "fallback"
        assert selection.selected_path == fallback.resolve()
        assert selection.selected_health is not None
        assert selection.selected_health.healthy is True
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_select_local_runtime_db_does_not_override_testing_context():
    tmp_path = _workspace_tmp_dir()
    try:
        primary = tmp_path / "hc_local_dev.db"
        fallback = tmp_path / "app_clean.db"
        _create_runtime_db(fallback)

        selection = select_local_runtime_db(
            env={
                "HELPCHAIN_TESTING": "1",
                "HC_DB_PATH": str(primary.resolve()),
            },
            root=tmp_path,
            primary_path=primary,
            fallback_path=fallback,
        )

        assert selection.apply_contract is False
        assert selection.selected_label == "configured"
        assert selection.selected_path == primary.resolve()
        assert "test environment" in selection.reason
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
