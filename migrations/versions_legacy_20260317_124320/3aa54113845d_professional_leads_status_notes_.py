"""professional leads status notes contacted_at

Revision ID: 3aa54113845d
Revises: 64a3e8359c2e
Create Date: 2026-02-13 10:55:13.979315
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3aa54113845d"
down_revision = "64a3e8359c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "professional_leads" not in table_names:
        raise RuntimeError("professional_leads must exist before 3aa54113845d")

    columns = {col["name"] for col in inspector.get_columns("professional_leads")}

    if "status" not in columns:
        op.add_column(
            "professional_leads",
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default=sa.text("'new'"),
            ),
        )

    if "notes" not in columns:
        op.add_column(
            "professional_leads",
            sa.Column("notes", sa.Text(), nullable=True),
        )

    if "contacted_at" not in columns:
        op.add_column(
            "professional_leads",
            sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.execute("UPDATE professional_leads SET status = 'new' WHERE status IS NULL")

    index_names = {idx["name"] for idx in sa.inspect(bind).get_indexes("professional_leads")}
    if "ix_professional_leads_status" not in index_names:
        op.create_index(
            "ix_professional_leads_status",
            "professional_leads",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    # Keep downgrade non-destructive.
    pass
