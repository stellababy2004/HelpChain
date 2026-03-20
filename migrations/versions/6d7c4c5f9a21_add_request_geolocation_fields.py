"""add_request_geolocation_fields

Revision ID: 6d7c4c5f9a21
Revises: 2086039276b7
Create Date: 2026-03-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6d7c4c5f9a21"
down_revision = "2086039276b7"
branch_labels = None
depends_on = None


def _request_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("requests")}


def upgrade():
    existing = _request_columns()
    if "address_line" not in existing:
        op.add_column("requests", sa.Column("address_line", sa.String(length=255), nullable=True))
    if "postcode" not in existing:
        op.add_column("requests", sa.Column("postcode", sa.String(length=32), nullable=True))
    if "country" not in existing:
        op.add_column("requests", sa.Column("country", sa.String(length=120), nullable=True))
    if "normalized_address" not in existing:
        op.add_column(
            "requests",
            sa.Column("normalized_address", sa.String(length=500), nullable=True),
        )
    if "geocoding_status" not in existing:
        op.add_column(
            "requests",
            sa.Column(
                "geocoding_status",
                sa.String(length=32),
                nullable=True,
                server_default=sa.text("'incomplete'"),
            ),
        )


def downgrade():
    existing = _request_columns()
    if "geocoding_status" in existing:
        op.drop_column("requests", "geocoding_status")
    if "normalized_address" in existing:
        op.drop_column("requests", "normalized_address")
    if "country" in existing:
        op.drop_column("requests", "country")
    if "postcode" in existing:
        op.drop_column("requests", "postcode")
    if "address_line" in existing:
        op.drop_column("requests", "address_line")
