"""add pending organization signup state"""

from alembic import op
import sqlalchemy as sa


revision = "20261026_1200"
down_revision = "19b787489955"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_organization_signups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=160), nullable=False),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("organization_type", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("verification_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pending_organization_signups_email", "pending_organization_signups", ["email"])
    op.create_index("ix_pending_organization_signups_token_hash", "pending_organization_signups", ["verification_token_hash"], unique=True)
    op.create_index("ix_pending_organization_signups_expires_at", "pending_organization_signups", ["expires_at"])
    op.create_index("ix_pending_organization_signups_consumed_at", "pending_organization_signups", ["consumed_at"])


def downgrade():
    op.drop_table("pending_organization_signups")
