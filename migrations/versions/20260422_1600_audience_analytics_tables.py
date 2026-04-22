"""add audience analytics tables

Revision ID: 20260422_1600
Revises: 20260422_1430
Create Date: 2026-04-22 16:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260422_1600"
down_revision = "20260422_1430"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        return any(
            idx.get("name") == index_name
            for idx in inspect(bind).get_indexes(table_name)
        )
    except Exception:
        return False


def _create_index_once(bind, index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _has_index(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, "analytics_events"):
        op.create_table(
            "analytics_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("event_category", sa.String(length=100), nullable=True),
            sa.Column("event_action", sa.String(length=100), nullable=True),
            sa.Column("event_label", sa.String(length=255), nullable=True),
            sa.Column("event_value", sa.Integer(), nullable=True),
            sa.Column("user_session", sa.String(length=128), nullable=True),
            sa.Column("user_type", sa.String(length=50), nullable=True),
            sa.Column("user_ip", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("page_url", sa.String(length=500), nullable=True),
            sa.Column("page_title", sa.String(length=255), nullable=True),
            sa.Column("referrer", sa.String(length=500), nullable=True),
            sa.Column("load_time", sa.Float(), nullable=True),
            sa.Column("screen_resolution", sa.String(length=20), nullable=True),
            sa.Column("device_type", sa.String(length=50), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_analytics_events_event_type", ["event_type"]),
        ("ix_analytics_events_created_at", ["created_at"]),
        ("ix_analytics_events_page_url", ["page_url"]),
        ("ix_analytics_events_user_session", ["user_session"]),
        ("ix_analytics_events_event_type_created_at", ["event_type", "created_at"]),
    ):
        _create_index_once(bind, index_name, "analytics_events", columns)

    if not _has_table(bind, "user_behaviors"):
        op.create_table(
            "user_behaviors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("user_type", sa.String(length=50), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("device_info", sa.String(length=100), nullable=True),
            sa.Column("location", sa.String(length=100), nullable=True),
            sa.Column(
                "session_start",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "last_activity",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("total_time_spent", sa.Integer(), nullable=True),
            sa.Column("pages_visited", sa.Integer(), nullable=True),
            sa.Column("entry_page", sa.String(length=500), nullable=True),
            sa.Column("exit_page", sa.String(length=500), nullable=True),
            sa.Column("bounce_rate", sa.Boolean(), nullable=True),
            sa.Column("conversion_action", sa.String(length=100), nullable=True),
            sa.Column("pages_sequence", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", name="uq_user_behaviors_session_id"),
        )

    for index_name, columns in (
        ("ix_user_behaviors_session_id", ["session_id"]),
        ("ix_user_behaviors_session_start", ["session_start"]),
        ("ix_user_behaviors_last_activity", ["last_activity"]),
        ("ix_user_behaviors_location", ["location"]),
    ):
        _create_index_once(bind, index_name, "user_behaviors", columns)


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, "user_behaviors"):
        op.drop_table("user_behaviors")
    if _has_table(bind, "analytics_events"):
        op.drop_table("analytics_events")
