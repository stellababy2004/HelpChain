from pathlib import Path


def test_audience_analytics_migration_declares_required_tables_and_indexes():
    migration = Path("migrations/versions/20260422_1600_audience_analytics_tables.py")
    content = migration.read_text(encoding="utf-8")

    assert 'revision = "20260422_1600"' in content
    assert 'down_revision = "20260422_1430"' in content
    assert '"analytics_events"' in content
    assert '"user_behaviors"' in content
    assert "ix_analytics_events_event_type" in content
    assert "ix_analytics_events_created_at" in content
    assert "ix_analytics_events_page_url" in content
    assert "ix_analytics_events_user_session" in content
    assert "ix_user_behaviors_session_id" in content
