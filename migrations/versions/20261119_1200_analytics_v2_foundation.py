"""Add Analytics v2 identity and scope fields.

Revision ID: 20261119_1200
Revises: 20261112_1200
"""

from alembic import op
import sqlalchemy as sa

revision = "20261119_1200"
down_revision = "20261112_1200"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("analytics_events") as batch:
        batch.add_column(sa.Column("event_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("analytics_scope", sa.String(40), nullable=True))
        batch.add_column(sa.Column("properties_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("visitor_id", sa.String(128), nullable=True))

    op.create_index(
        "uq_analytics_events_structure_event",
        "analytics_events",
        ["structure_id", "event_id"],
        unique=True,
    )
    op.create_index(
        "ix_analytics_events_scope_created_at",
        "analytics_events",
        ["analytics_scope", "created_at"],
    )
    op.create_index(
        "ix_analytics_events_visitor_created_at",
        "analytics_events",
        ["visitor_id", "created_at"],
    )

    with op.batch_alter_table("user_behaviors") as batch:
        batch.add_column(sa.Column("visitor_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("analytics_scope", sa.String(40), nullable=True))

    op.create_index(
        "ix_user_behaviors_visitor_id",
        "user_behaviors",
        ["visitor_id"],
    )


def downgrade():
    op.drop_index("ix_user_behaviors_visitor_id", table_name="user_behaviors")
    with op.batch_alter_table("user_behaviors") as batch:
        batch.drop_column("analytics_scope")
        batch.drop_column("visitor_id")

    op.drop_index(
        "ix_analytics_events_visitor_created_at", table_name="analytics_events"
    )
    op.drop_index("ix_analytics_events_scope_created_at", table_name="analytics_events")
    op.drop_index("uq_analytics_events_structure_event", table_name="analytics_events")

    with op.batch_alter_table("analytics_events") as batch:
        batch.drop_column("visitor_id")
        batch.drop_column("properties_json")
        batch.drop_column("analytics_scope")
        batch.drop_column("event_id")
