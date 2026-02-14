"""create requests table bootstrap

Revision ID: 0f9f6e1e9c10
Revises: add_lat_lng_volunteer
Create Date: 2026-02-14 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0f9f6e1e9c10"
down_revision = "add_lat_lng_volunteer"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "requests" in inspector.get_table_names():
        return

    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=200), nullable=True),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("location_text", sa.String(length=500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=True),
        sa.Column(
            "category",
            sa.String(length=32),
            nullable=False,
            server_default="general",
        ),
        sa.Column("source_channel", sa.String(length=100), nullable=True),
        sa.Column("assigned_volunteer_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("owned_at", sa.DateTime(), nullable=True),
        sa.Column("requester_token_hash", sa.String(length=128), nullable=True),
        sa.Column("requester_token_created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_requests_category", "requests", ["category"], unique=False)
    op.create_index(
        "ix_requests_requester_token_hash",
        "requests",
        ["requester_token_hash"],
        unique=False,
    )
    op.create_index("ix_requests_owner_id", "requests", ["owner_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "requests" not in inspector.get_table_names():
        return

    op.drop_index("ix_requests_owner_id", table_name="requests")
    op.drop_index("ix_requests_requester_token_hash", table_name="requests")
    op.drop_index("ix_requests_category", table_name="requests")
    op.drop_table("requests")

