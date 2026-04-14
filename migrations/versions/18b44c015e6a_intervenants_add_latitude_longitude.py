"""intervenants: add latitude longitude

Revision ID: 18b44c015e6a
Revises: 89e64a6fbd28
Create Date: 2026-04-14 13:36:10.335788
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "18b44c015e6a"
down_revision = "89e64a6fbd28"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if not _has_column("intervenants", "latitude"):
        op.add_column(
            "intervenants",
            sa.Column("latitude", sa.Float(), nullable=True)
        )

    if not _has_column("intervenants", "longitude"):
        op.add_column(
            "intervenants",
            sa.Column("longitude", sa.Float(), nullable=True)
        )


def downgrade():
    if _has_column("intervenants", "longitude"):
        op.drop_column("intervenants", "longitude")

    if _has_column("intervenants", "latitude"):
        op.drop_column("intervenants", "latitude")