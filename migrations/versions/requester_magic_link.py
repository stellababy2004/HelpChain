"""add requester magic link fields"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "requester_magic_link"
down_revision = "add_roles_and_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("requests", sa.Column("requester_token_hash", sa.String(length=128), nullable=True))
    op.add_column("requests", sa.Column("requester_token_created_at", sa.DateTime(), nullable=True))
    op.create_index("ix_requests_requester_token_hash", "requests", ["requester_token_hash"], unique=False)


def downgrade():
    op.drop_index("ix_requests_requester_token_hash", table_name="requests")
    op.drop_column("requests", "requester_token_created_at")
    op.drop_column("requests", "requester_token_hash")
