"""Store sanitized organization logos in PostgreSQL."""

import sqlalchemy as sa
from alembic import op


revision = "20261112_1200"
down_revision = "20261102_1200_admin_temporary_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_logos",
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("structures.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("png_data", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("organization_logos")
