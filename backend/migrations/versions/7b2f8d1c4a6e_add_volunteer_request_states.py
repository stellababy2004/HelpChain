"""add volunteer_request_states

Revision ID: 7b2f8d1c4a6e
Revises: c4b7e2a1d940
Create Date: 2026-02-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7b2f8d1c4a6e"
down_revision = "c4b7e2a1d940"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteer_request_states" in inspector.get_table_names():
        return

    op.create_table(
        "volunteer_request_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("volunteer_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
        sa.ForeignKeyConstraint(["volunteer_id"], ["volunteers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volunteer_id", "request_id", name="uq_volunteer_request_state"),
    )
    op.create_index(
        op.f("ix_volunteer_request_states_volunteer_id"),
        "volunteer_request_states",
        ["volunteer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_volunteer_request_states_request_id"),
        "volunteer_request_states",
        ["request_id"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteer_request_states" not in inspector.get_table_names():
        return

    op.drop_index(op.f("ix_volunteer_request_states_request_id"), table_name="volunteer_request_states")
    op.drop_index(op.f("ix_volunteer_request_states_volunteer_id"), table_name="volunteer_request_states")
    op.drop_table("volunteer_request_states")

