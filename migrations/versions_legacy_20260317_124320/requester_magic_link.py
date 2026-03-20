"""add requester magic link fields"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index

# revision identifiers, used by Alembic.
# NOTE: this project DB was already stamped with this revision id in existing environments.
# Keep it stable so `flask db upgrade` can continue the chain.
revision = "6b9c56545b8a"
down_revision = "add_roles_and_audit"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "requests" not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns("requests")}
    if "requester_token_hash" not in cols:
        op.add_column(
            "requests", sa.Column("requester_token_hash", sa.String(length=128), nullable=True)
        )
    if "requester_token_created_at" not in cols:
        op.add_column(
            "requests", sa.Column("requester_token_created_at", sa.DateTime(), nullable=True)
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("requests")}
    if "ix_requests_requester_token_hash" not in indexes:
        op.create_index(
            "ix_requests_requester_token_hash",
            "requests",
            ["requester_token_hash"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "requests" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("requests")}
    if "ix_requests_requester_token_hash" in indexes:
        safe_drop_index(op, "ix_requests_requester_token_hash", table_name="requests")

    cols = {c["name"] for c in inspector.get_columns("requests")}
    if "requester_token_created_at" in cols:
        safe_drop_column(op, "requests", "requester_token_created_at")
    if "requester_token_hash" in cols:
        safe_drop_column(op, "requests", "requester_token_hash")