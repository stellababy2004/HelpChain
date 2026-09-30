"""Add admin user invitations.

Revision ID: 20260930_0600
Revises: 20260927_2200
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_0600"
down_revision = "20260927_2200"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_user_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("structures.id"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_admin_user_invitations_token_hash"),
    )

    op.create_index(
        "ix_admin_user_invitations_structure_id",
        "admin_user_invitations",
        ["structure_id"],
    )
    op.create_index(
        "ix_admin_user_invitations_email",
        "admin_user_invitations",
        ["email"],
    )


def downgrade():
    op.drop_index(
        "ix_admin_user_invitations_email",
        table_name="admin_user_invitations",
    )
    op.drop_index(
        "ix_admin_user_invitations_structure_id",
        table_name="admin_user_invitations",
    )
    op.drop_table("admin_user_invitations")
