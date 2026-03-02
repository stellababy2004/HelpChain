"""add volunteer_actions table for admin requests views

Revision ID: c3f9d1a7b2e4
Revises: a1d4f2c9e8b7
Create Date: 2026-03-02 13:35:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3f9d1a7b2e4"
down_revision = "a1d4f2c9e8b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "volunteer_actions" in existing_tables:
        return

    op.create_table(
        "volunteer_actions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("volunteer_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
        sa.ForeignKeyConstraint(["volunteer_id"], ["volunteers.id"]),
        sa.UniqueConstraint(
            "request_id",
            "volunteer_id",
            name="uq_volunteer_action_request_volunteer",
        ),
    )

    op.create_index(
        "ix_volunteer_actions_request_id",
        "volunteer_actions",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_volunteer_actions_volunteer_id",
        "volunteer_actions",
        ["volunteer_id"],
        unique=False,
    )
    op.create_index(
        "ix_volunteer_actions_action",
        "volunteer_actions",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_volunteer_actions_request_id_action",
        "volunteer_actions",
        ["request_id", "action"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "volunteer_actions" not in existing_tables:
        return

    for idx in (
        "ix_volunteer_actions_request_id_action",
        "ix_volunteer_actions_action",
        "ix_volunteer_actions_volunteer_id",
        "ix_volunteer_actions_request_id",
    ):
        op.drop_index(idx, table_name="volunteer_actions")
    op.drop_table("volunteer_actions")
