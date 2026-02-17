"""create admin_users table

Revision ID: c4b7e2a1d940
Revises: 9c6b7a2b0a77
Create Date: 2026-02-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4b7e2a1d940"
down_revision = "9c6b7a2b0a77"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "admin_users" in inspector.get_table_names():
        return

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=True, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("totp_secret", sa.String(length=32), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("mfa_enrolled_at", sa.DateTime(), nullable=True),
        sa.Column("backup_codes_hashes", sa.Text(), nullable=True),
        sa.Column("backup_codes_generated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "admin_users" not in inspector.get_table_names():
        return
    op.drop_table("admin_users")

