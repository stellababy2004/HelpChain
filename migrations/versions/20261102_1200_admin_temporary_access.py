"""Add versioned admin sessions and temporary password expiry metadata."""

from alembic import op
import sqlalchemy as sa


revision = "20261102_1200_admin_temporary_access"
down_revision = "20261027_1200"
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    return column in {row["name"] for row in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, "admin_users", "auth_version"):
        op.add_column(
            "admin_users",
            sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_column(bind, "admin_users", "temporary_password_expires_at"):
        op.add_column(
            "admin_users",
            sa.Column("temporary_password_expires_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, "admin_users", "temporary_password_expires_at"):
        op.drop_column("admin_users", "temporary_password_expires_at")
    if _has_column(bind, "admin_users", "auth_version"):
        op.drop_column("admin_users", "auth_version")
