from __future__ import annotations

from pathlib import Path

import pytest

from scripts import migration_guard


def _write_revision(versions_dir: Path, revision: str, down_revision: str | None) -> None:
    down_value = repr(down_revision) if down_revision is not None else "None"
    (versions_dir / f"{revision}.py").write_text(
        "\n".join(
            [
                f'revision = "{revision}"',
                f"down_revision = {down_value}",
                "branch_labels = None",
                "depends_on = None",
                "",
                "def upgrade():",
                "    pass",
                "",
                "def downgrade():",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _alembic_fixture(tmp_path: Path, revisions: list[tuple[str, str | None]]) -> Path:
    migration_dir = tmp_path / "migrations"
    versions_dir = migration_dir / "versions"
    versions_dir.mkdir(parents=True)
    for revision, down_revision in revisions:
        _write_revision(versions_dir, revision, down_revision)

    ini = tmp_path / "alembic.ini"
    ini.write_text(
        f"[alembic]\nscript_location = {migration_dir.as_posix()}\n",
        encoding="utf-8",
    )
    return ini


def _migration(tmp_path: Path, upgrade_body: str, downgrade_body: str = "pass") -> Path:
    path = tmp_path / "changed_migration.py"
    path.write_text(
        "\n".join(
            [
                "def upgrade():",
                *[f"    {line}" for line in upgrade_body.splitlines()],
                "",
                "def downgrade():",
                *[f"    {line}" for line in downgrade_body.splitlines()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_one_alembic_head_passes(tmp_path):
    ini = _alembic_fixture(tmp_path, [("base", None), ("head", "base")])
    result = migration_guard.validate_alembic_heads(ini)
    assert result.errors == []


def test_multiple_alembic_heads_fail(tmp_path):
    ini = _alembic_fixture(tmp_path, [("base", None), ("left", "base"), ("right", "base")])
    result = migration_guard.validate_alembic_heads(ini)
    assert result.errors
    assert "found 2" in result.errors[0]


def test_safe_changed_migration_passes(tmp_path):
    path = _migration(tmp_path, 'op.add_column("requests", sa.Column("note", sa.Text()))')
    result = migration_guard.scan_migration_file(path)
    assert result.errors == []


@pytest.mark.parametrize(
    "upgrade_body, expected",
    [
        ('op.drop_table("requests")', "op.drop_table"),
        ('op.drop_column("requests", "legacy")', "op.drop_column"),
        ('op.execute("DROP TABLE requests")', "DROP TABLE"),
        ('op.execute("ALTER TABLE requests DROP COLUMN legacy")', "DROP COLUMN"),
        ('op.execute("DELETE FROM requests")', "DELETE FROM"),
        ('op.execute("TRUNCATE requests")', "TRUNCATE"),
    ],
)
def test_destructive_changed_migration_fails(tmp_path, upgrade_body, expected):
    path = _migration(tmp_path, upgrade_body)
    result = migration_guard.scan_migration_file(path)
    assert any(expected in error for error in result.errors)


def test_destructive_downgrade_does_not_create_upgrade_failure(tmp_path):
    path = _migration(tmp_path, "pass", 'op.drop_table("requests")')
    result = migration_guard.scan_migration_file(path)
    assert result.errors == []


def test_destructive_words_outside_upgrade_do_not_create_false_positive(tmp_path):
    path = _migration(tmp_path, "# DROP TABLE is mentioned only in this comment\npass")
    original = path.read_text(encoding="utf-8")
    path.write_text(
        'NOTICE = "DROP TABLE is documentation, not executable migration SQL"\n\n' + original,
        encoding="utf-8",
    )

    result = migration_guard.scan_migration_file(path)

    assert result.errors == []


def test_unchanged_legacy_migration_does_not_block(tmp_path):
    ini = _alembic_fixture(tmp_path, [("head", None)])
    _migration(tmp_path, 'op.drop_table("legacy_table")')
    result = migration_guard.run_guard([], ini)
    assert result.errors == []


def test_warning_only_patterns_do_not_fail(tmp_path):
    path = _migration(
        tmp_path,
        "\n".join(
            [
                'op.alter_column("requests", "status")',
                'with op.batch_alter_table("requests"):',
                "    pass",
                'op.add_column("requests", sa.Column("required", sa.Text(), nullable=False))',
                'op.drop_index("ix_requests_status")',
            ]
        ),
        downgrade_body="pass",
    )
    result = migration_guard.scan_migration_file(path)
    assert result.errors == []
    assert len(result.warnings) == 5
