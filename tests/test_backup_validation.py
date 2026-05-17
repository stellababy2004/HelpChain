from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from scripts.validate_backup_set import _validate


def _write_backup_set(tmp_path: Path, *, body: bytes):
    backup = tmp_path / "helpchain_prod_20260517T120000Z.sql.gz"
    with gzip.open(backup, "wb") as fh:
        fh.write(body)

    sha = hashlib.sha256(backup.read_bytes()).hexdigest()
    checksum = tmp_path / f"{backup.name}.sha256"
    checksum.write_text(f"{sha}  {backup.name}\n", encoding="utf-8")

    manifest = tmp_path / f"{backup.name}.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backup_file": backup.name,
                "sha256": sha,
                "size_bytes": backup.stat().st_size,
                "generated_at_utc": "2026-05-17T12:00:00Z",
                "repository": "owner/helpchain",
                "git_sha": "abcdef1234567890",
                "s3_key_backup": f"postgres/{backup.name}",
                "s3_key_checksum": f"postgres/{backup.name}.sha256",
                "s3_key_manifest": f"postgres/{backup.name}.manifest.json",
            }
        ),
        encoding="utf-8",
    )
    return backup, checksum, manifest


def test_backup_validator_accepts_plain_postgres_sql_gzip(tmp_path):
    backup, checksum, manifest = _write_backup_set(
        tmp_path,
        body=(
            b"--\n-- PostgreSQL database dump\n--\n"
            b"SET statement_timeout = 0;\n"
            b"CREATE TABLE public.requests (id integer);\n"
        ),
    )

    errors = _validate(
        backup_path=backup,
        checksum_path=checksum,
        manifest_path=manifest,
        expected_repository="owner/helpchain",
    )

    assert errors == []


def test_backup_validator_rejects_non_sql_gzip_payload(tmp_path):
    backup, checksum, manifest = _write_backup_set(
        tmp_path,
        body=b"this is compressed but not a PostgreSQL dump",
    )

    errors = _validate(
        backup_path=backup,
        checksum_path=checksum,
        manifest_path=manifest,
        expected_repository="owner/helpchain",
    )

    assert "backup gzip does not look like a plain PostgreSQL SQL dump" in errors

