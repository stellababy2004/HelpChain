"""add social_requests (demande intake)

Revision ID: 52be7e2671ae
Revises: e9c4b7a2d1f0
Create Date: 2026-03-05 09:31:26.226677

"""
from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import (
    safe_create_index,
    safe_drop_column,
    safe_drop_constraint,
    safe_drop_index,
)


# revision identifiers, used by Alembic.
revision = '52be7e2671ae'
down_revision = 'e9c4b7a2d1f0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "social_requests" not in tables:
        op.create_table(
            "social_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("structure_id", sa.Integer(), sa.ForeignKey("structures.id"), nullable=False),
            sa.Column("need_type", sa.String(length=64), nullable=False),
            sa.Column("urgency", sa.String(length=16), nullable=False, server_default="medium"),
            sa.Column("person_ref", sa.String(length=128), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
            sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    safe_create_index(op, "social_requests", "ix_social_requests_structure_id", ["structure_id"])
    safe_create_index(op, "social_requests", "ix_social_requests_assigned_to_user_id", ["assigned_to_user_id"])
    safe_create_index(op, "social_requests", "ix_social_requests_created_at", ["created_at"])
    safe_create_index(
        op,
        "social_requests",
        "ix_social_requests_struct_status_created",
        ["structure_id", "status", "created_at"],
    )
    safe_create_index(
        op,
        "social_requests",
        "ix_social_requests_status_urgency",
        ["status", "urgency"],
    )


def downgrade():
    safe_drop_index(op, "ix_social_requests_status_urgency", table_name="social_requests")
    safe_drop_index(op, "ix_social_requests_struct_status_created", table_name="social_requests")
    safe_drop_index(op, "ix_social_requests_created_at", table_name="social_requests")
    safe_drop_index(op, "ix_social_requests_assigned_to_user_id", table_name="social_requests")
    safe_drop_index(op, "ix_social_requests_structure_id", table_name="social_requests")
    op.drop_table("social_requests")
