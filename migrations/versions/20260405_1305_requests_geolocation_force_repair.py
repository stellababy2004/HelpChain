"""requests geolocation force repair

Revision ID: 20260405_1305
Revises: 20260405_1245
Create Date: 2026-04-05 13:05:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260405_1305"
down_revision = "20260405_1245"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        insp = inspect(bind)
        cols = insp.get_columns(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(c.get("name") == column_name for c in cols)


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        op.add_column("requests", sa.Column("address_line", sa.String(length=255), nullable=True))
        op.add_column("requests", sa.Column("postcode", sa.String(length=32), nullable=True))
        op.add_column("requests", sa.Column("country", sa.String(length=120), nullable=True))
        op.add_column(
            "requests",
            sa.Column("normalized_address", sa.String(length=500), nullable=True),
        )
        op.add_column(
            "requests",
            sa.Column(
                "geocoding_status",
                sa.String(length=32),
                nullable=True,
                server_default=sa.text("'incomplete'"),
            ),
        )
        return

    if not _has_table(bind, "requests"):
        return

    if not _has_column(bind, "requests", "address_line"):
        op.add_column("requests", sa.Column("address_line", sa.String(length=255), nullable=True))
    if not _has_column(bind, "requests", "postcode"):
        op.add_column("requests", sa.Column("postcode", sa.String(length=32), nullable=True))
    if not _has_column(bind, "requests", "country"):
        op.add_column("requests", sa.Column("country", sa.String(length=120), nullable=True))
    if not _has_column(bind, "requests", "normalized_address"):
        op.add_column(
            "requests",
            sa.Column("normalized_address", sa.String(length=500), nullable=True),
        )
    if not _has_column(bind, "requests", "geocoding_status"):
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
    # Data-safe downgrade: keep repaired request columns once created.
    pass
