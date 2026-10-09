import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import sqlalchemy as sa


def test_website_analytics_migration_preserves_unassigned_history(monkeypatch):
    path = Path("migrations/versions/20261001_1000_website_analytics_tenant.py")
    spec = importlib.util.spec_from_file_location("website_analytics_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE structures (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text(
            "CREATE TABLE analytics_events (id INTEGER PRIMARY KEY, event_type VARCHAR(100) NOT NULL)"
        ))
        connection.execute(sa.text("INSERT INTO analytics_events VALUES (1, 'page_view')"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert connection.execute(sa.text("SELECT structure_id FROM analytics_events WHERE id = 1")).one() == (None,)
        assert "ix_analytics_events_structure_id" in {i["name"] for i in inspector.get_indexes("analytics_events")}
        assert any(fk["referred_table"] == "structures" for fk in inspector.get_foreign_keys("analytics_events"))
        migration.downgrade()
        assert connection.execute(sa.text("SELECT * FROM analytics_events")).one() == (1, "page_view")
        assert "structure_id" not in {c["name"] for c in sa.inspect(connection).get_columns("analytics_events")}
    engine.dispose()


def test_website_analytics_revision_is_the_single_head():
    assert ScriptDirectory("migrations").get_heads() == ["20261008_1200"]
