from pathlib import Path

from alembic.script import ScriptDirectory


def test_long_admin_revision_is_preceded_by_version_column_widening():
    script = ScriptDirectory("migrations")
    widening = script.get_revision("20261027_1200")
    admin_access = script.get_revision("20261102_1200_admin_temporary_access")

    assert widening.down_revision == "20261026_1200"
    assert admin_access.down_revision == widening.revision
    assert len(admin_access.revision) > 32

    migration = Path("migrations/versions/20261027_1200_widen_alembic_version.py").read_text(encoding="utf-8")
    assert '"version_num"' in migration
    assert "length=255" in migration
