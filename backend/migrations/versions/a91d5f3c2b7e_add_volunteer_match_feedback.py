"""add volunteer_match_feedback

Revision ID: a91d5f3c2b7e
Revises: 7b2f8d1c4a6e
Create Date: 2026-02-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a91d5f3c2b7e"
down_revision = "7b2f8d1c4a6e"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteer_match_feedback" in inspector.get_table_names():
        return

    op.create_table(
        "volunteer_match_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("volunteer_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
        sa.ForeignKeyConstraint(["volunteer_id"], ["volunteers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volunteer_id", "request_id", name="uq_vol_req_feedback"),
    )
    op.create_index(
        op.f("ix_volunteer_match_feedback_volunteer_id"),
        "volunteer_match_feedback",
        ["volunteer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_volunteer_match_feedback_request_id"),
        "volunteer_match_feedback",
        ["request_id"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteer_match_feedback" not in inspector.get_table_names():
        return

    op.drop_index(
        op.f("ix_volunteer_match_feedback_request_id"),
        table_name="volunteer_match_feedback",
    )
    op.drop_index(
        op.f("ix_volunteer_match_feedback_volunteer_id"),
        table_name="volunteer_match_feedback",
    )
    op.drop_table("volunteer_match_feedback")

