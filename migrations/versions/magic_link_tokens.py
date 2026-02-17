"""add magic_link_tokens table

Production-correct single-use magic links with TTL, hashed token storage.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "magic_link_tokens"
down_revision = "6b9c56545b8a"
branch_labels = None
depends_on = None


def upgrade():
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
    op.create_index(
        "ix_magic_link_tokens_token_hash",
        "magic_link_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_magic_link_tokens_purpose",
        "magic_link_tokens",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_magic_link_tokens_email",
        "magic_link_tokens",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_magic_link_tokens_request_id",
        "magic_link_tokens",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_magic_link_tokens_expires_at",
        "magic_link_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_magic_link_tokens_used_at",
        "magic_link_tokens",
        ["used_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_magic_link_tokens_used_at", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_expires_at", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_request_id", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_email", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_purpose", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_token_hash", table_name="magic_link_tokens")
    op.drop_table("magic_link_tokens")
