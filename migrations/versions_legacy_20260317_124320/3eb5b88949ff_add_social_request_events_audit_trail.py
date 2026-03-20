"""add social request events audit trail

Revision ID: 3eb5b88949ff
Revises: 52be7e2671ae
Create Date: 2026-03-05 10:18:52.059869

"""
from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index


# revision identifiers, used by Alembic.
revision = '3eb5b88949ff'
down_revision = '52be7e2671ae'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "social_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("social_requests.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_social_request_events_request_id",
        "social_request_events",
        ["request_id"],
    )
    op.create_index(
        "ix_social_request_events_created_at",
        "social_request_events",
        ["created_at"],
    )
    op.create_index(
        "ix_social_request_events_actor_user_id",
        "social_request_events",
        ["actor_user_id"],
    )


def downgrade():
    safe_drop_index(op, "ix_social_request_events_actor_user_id", table_name="social_request_events")
    safe_drop_index(op, "ix_social_request_events_created_at", table_name="social_request_events")
    safe_drop_index(op, "ix_social_request_events_request_id", table_name="social_request_events")
    op.drop_table("social_request_events")