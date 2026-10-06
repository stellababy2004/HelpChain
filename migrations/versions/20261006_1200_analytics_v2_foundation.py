"""Add Analytics v2 identity and scope foundation.

Revision ID: 20261006_1200
Revises: 20261001_1000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261006_1200"
down_revision = "20261001_1000"
branch_labels = None
depends_on = None


def _columns(bind, table_name: str) -> set[str]:
    try:
        return {column["name"] for column in inspect(bind).get_columns(table_name)}
    except Exception:
        return set()


def _indexes(bind, table_name: str) -> set[str]:
    try:
        return {index["name"] for index in inspect(bind).get_indexes(table_name)}
    except Exception:
        return set()


def _add_column_once(bind, table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(bind, table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(column)


def _create_index_once(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if index_name not in _indexes(bind, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    bind = op.get_bind()

    for column in (
        sa.Column("event_id", sa.String(length=128), nullable=True),
        sa.Column("analytics_scope", sa.String(length=40), nullable=True),
        sa.Column("properties_json", sa.Text(), nullable=True),
        sa.Column("visitor_id", sa.String(length=128), nullable=True),
    ):
        _add_column_once(bind, "analytics_events", column)

    for index_name, columns, unique in (
        ("uq_analytics_events_event_id", ["event_id"], True),
        ("ix_analytics_events_analytics_scope", ["analytics_scope"], False),
        ("ix_analytics_events_visitor_id", ["visitor_id"], False),
        ("ix_analytics_events_scope_created_at", ["analytics_scope", "created_at"], False),
        ("ix_analytics_events_visitor_created_at", ["visitor_id", "created_at"], False),
        ("ix_analytics_events_session_created_at", ["user_session", "created_at"], False),
    ):
        _create_index_once(bind, index_name, "analytics_events", columns, unique=unique)

    for column in (
        sa.Column("visitor_id", sa.String(length=128), nullable=True),
        sa.Column("analytics_scope", sa.String(length=40), nullable=True),
    ):
        _add_column_once(bind, "user_behaviors", column)

    for index_name, columns in (
        ("ix_user_behaviors_visitor_id", ["visitor_id"]),
        ("ix_user_behaviors_analytics_scope", ["analytics_scope"]),
    ):
        _create_index_once(bind, index_name, "user_behaviors", columns)


def downgrade():
    bind = op.get_bind()
    for index_name, table_name in (
        ("ix_user_behaviors_analytics_scope", "user_behaviors"),
        ("ix_user_behaviors_visitor_id", "user_behaviors"),
        ("ix_analytics_events_session_created_at", "analytics_events"),
        ("ix_analytics_events_visitor_created_at", "analytics_events"),
        ("ix_analytics_events_scope_created_at", "analytics_events"),
        ("ix_analytics_events_visitor_id", "analytics_events"),
        ("ix_analytics_events_analytics_scope", "analytics_events"),
        ("uq_analytics_events_event_id", "analytics_events"),
    ):
        if index_name in _indexes(bind, table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name, column_names in (
        ("user_behaviors", ("analytics_scope", "visitor_id")),
        ("analytics_events", ("visitor_id", "properties_json", "analytics_scope", "event_id")),
    ):
        existing = _columns(bind, table_name)
        with op.batch_alter_table(table_name) as batch:
            for column_name in column_names:
                if column_name in existing:
                    batch.drop_column(column_name)
