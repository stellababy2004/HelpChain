from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


REQUIRED_MANIFEST_FIELDS = (
    "backup_file",
    "sha256",
    "size_bytes",
    "generated_at_utc",
    "repository",
    "git_sha",
    "s3_key_backup",
    "s3_key_checksum",
    "s3_key_manifest",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_checksum_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("checksum file is empty")
    token = raw.split()[0].strip()
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", token):
        raise ValueError("checksum file does not contain a valid sha256 token")
    return token.lower()


def _parse_iso8601(value: str) -> None:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    datetime.fromisoformat(v)


def _validate(
    *,
    backup_path: Path,
    checksum_path: Path,
    manifest_path: Path,
    expected_repository: str | None,
) -> list[str]:
    errors: list[str] = []

    if not backup_path.exists():
        errors.append(f"missing backup file: {backup_path}")
    if not checksum_path.exists():
        errors.append(f"missing checksum file: {checksum_path}")
    if not manifest_path.exists():
        errors.append(f"missing manifest file: {manifest_path}")
    if errors:
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid manifest json: {exc}")
        return errors

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"manifest missing required field: {field}")

    if errors:
        return errors

    backup_name = backup_path.name
    backup_size = backup_path.stat().st_size
    manifest_backup_file = str(manifest.get("backup_file", "")).strip()
    manifest_sha256 = str(manifest.get("sha256", "")).strip().lower()
    manifest_size = int(manifest.get("size_bytes", -1))
    manifest_repo = str(manifest.get("repository", "")).strip()
    manifest_git_sha = str(manifest.get("git_sha", "")).strip()
    manifest_s3_backup = str(manifest.get("s3_key_backup", "")).strip()
    manifest_s3_checksum = str(manifest.get("s3_key_checksum", "")).strip()
    manifest_s3_manifest = str(manifest.get("s3_key_manifest", "")).strip()

    if manifest_backup_file != backup_name:
        errors.append(
            f"manifest backup_file mismatch: expected {backup_name}, got {manifest_backup_file}"
        )

    checksum_file_sha = _read_checksum_file(checksum_path)
    computed_sha = _sha256_file(backup_path)
    if checksum_file_sha != computed_sha:
        errors.append(
            f"checksum mismatch: checksum_file={checksum_file_sha} computed={computed_sha}"
        )
    if manifest_sha256 != computed_sha:
        errors.append(
            f"manifest sha256 mismatch: manifest={manifest_sha256} computed={computed_sha}"
        )

    if manifest_size != backup_size:
        errors.append(
            f"manifest size_bytes mismatch: manifest={manifest_size} actual={backup_size}"
        )

    try:
        _parse_iso8601(str(manifest.get("generated_at_utc", "")))
    except Exception as exc:
        errors.append(f"invalid generated_at_utc: {exc}")

    if expected_repository and manifest_repo != expected_repository:
        errors.append(
            f"repository mismatch: expected={expected_repository} manifest={manifest_repo}"
        )

    if not re.fullmatch(r"[A-Fa-f0-9]{7,64}", manifest_git_sha):
        errors.append("manifest git_sha is missing or invalid")

    expected_s3_backup = f"postgres/{backup_name}"
    expected_s3_checksum = f"postgres/{backup_name}.sha256"
    expected_s3_manifest = f"postgres/{backup_name}.manifest.json"
    if manifest_s3_backup != expected_s3_backup:
        errors.append(
            f"s3_key_backup mismatch: expected={expected_s3_backup} manifest={manifest_s3_backup}"
        )
    if manifest_s3_checksum != expected_s3_checksum:
        errors.append(
            f"s3_key_checksum mismatch: expected={expected_s3_checksum} manifest={manifest_s3_checksum}"
        )
    if manifest_s3_manifest != expected_s3_manifest:
        errors.append(
            f"s3_key_manifest mismatch: expected={expected_s3_manifest} manifest={manifest_s3_manifest}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate backup set integrity")
    parser.add_argument("--backup", required=True, help="Path to .sql.gz file")
    parser.add_argument("--checksum", required=True, help="Path to .sha256 file")
    parser.add_argument("--manifest", required=True, help="Path to .manifest.json file")
    parser.add_argument(
        "--expected-repository",
        default="",
        help="Optional expected repository value (owner/repo)",
    )
    args = parser.parse_args()

    backup_path = Path(args.backup)
    checksum_path = Path(args.checksum)
    manifest_path = Path(args.manifest)

    if backup_path.exists():
        print("backup file present: yes")
    if checksum_path.exists():
        print("checksum file present: yes")
    if manifest_path.exists():
        print("manifest file present: yes")

    errors = _validate(
        backup_path=backup_path,
        checksum_path=checksum_path,
        manifest_path=manifest_path,
        expected_repository=(args.expected_repository or "").strip() or None,
    )
    if errors:
        print("backup integrity status: FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("checksum verification passed")
    print("manifest verification passed")
    print("backup integrity status: OK")
    print(f"backup={args.backup}")
    print(f"checksum={args.checksum}")
    print(f"manifest={args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
