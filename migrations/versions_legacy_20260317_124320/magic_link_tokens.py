"""add magic_link_tokens table

Production-correct single-use magic links with TTL, hashed token storage.
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index

# revision identifiers, used by Alembic.
revision = "magic_link_tokens"
down_revision = "6b9c56545b8a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "magic_link_tokens" not in tables:
        op.create_table(
            "magic_link_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("purpose", sa.String(length=32), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("used_ip", sa.String(length=64), nullable=True),
            sa.Column("used_ua", sa.String(length=255), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("magic_link_tokens")}
    if "ix_magic_link_tokens_token_hash" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_token_hash",
            "magic_link_tokens",
            ["token_hash"],
            unique=True,
        )
    if "ix_magic_link_tokens_purpose" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_purpose",
            "magic_link_tokens",
            ["purpose"],
            unique=False,
        )
    if "ix_magic_link_tokens_email" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_email",
            "magic_link_tokens",
            ["email"],
            unique=False,
        )
    if "ix_magic_link_tokens_request_id" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_request_id",
            "magic_link_tokens",
            ["request_id"],
            unique=False,
        )
    if "ix_magic_link_tokens_expires_at" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_expires_at",
            "magic_link_tokens",
            ["expires_at"],
            unique=False,
        )
    if "ix_magic_link_tokens_used_at" not in indexes:
        op.create_index(
            "ix_magic_link_tokens_used_at",
            "magic_link_tokens",
            ["used_at"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "magic_link_tokens" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("magic_link_tokens")}
    if "ix_magic_link_tokens_used_at" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_used_at", table_name="magic_link_tokens")
    if "ix_magic_link_tokens_expires_at" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_expires_at", table_name="magic_link_tokens")
    if "ix_magic_link_tokens_request_id" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_request_id", table_name="magic_link_tokens")
    if "ix_magic_link_tokens_email" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_email", table_name="magic_link_tokens")
    if "ix_magic_link_tokens_purpose" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_purpose", table_name="magic_link_tokens")
    if "ix_magic_link_tokens_token_hash" in indexes:
        safe_drop_index(op, "ix_magic_link_tokens_token_hash", table_name="magic_link_tokens")
    op.drop_table("magic_link_tokens")