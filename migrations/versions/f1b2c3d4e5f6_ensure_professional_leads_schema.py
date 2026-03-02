"""ensure professional_leads table/columns exist for admin screens

Revision ID: f1b2c3d4e5f6
Revises: e4b7a1c2d9f0
Create Date: 2026-03-02 15:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5f6"
down_revision = "e4b7a1c2d9f0"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {col.get("name") for col in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {idx.get("name") for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "professional_leads"):
        op.create_table(
            "professional_leads",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=160), nullable=True),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("profession", sa.String(length=120), nullable=False),
            sa.Column("organization", sa.String(length=160), nullable=True),
            sa.Column("availability", sa.String(length=80), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=True),
            sa.Column("locale", sa.String(length=10), nullable=True),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="new",
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    inspector = sa.inspect(bind)
    cols = _column_names(inspector, "professional_leads")
    if "status" not in cols:
        op.add_column(
            "professional_leads",
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="new",
            ),
        )
    if "notes" not in cols:
        op.add_column("professional_leads", sa.Column("notes", sa.Text(), nullable=True))
    if "contacted_at" not in cols:
        op.add_column(
            "professional_leads",
            sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = sa.inspect(bind)
    idx_names = _index_names(inspector, "professional_leads")
    if "ix_professional_leads_email" not in idx_names:
        op.create_index(
            "ix_professional_leads_email",
            "professional_leads",
            ["email"],
            unique=False,
        )
    if "ix_professional_leads_city" not in idx_names:
        op.create_index(
            "ix_professional_leads_city",
            "professional_leads",
            ["city"],
            unique=False,
        )
    if "ix_professional_leads_profession" not in idx_names:
        op.create_index(
            "ix_professional_leads_profession",
            "professional_leads",
            ["profession"],
            unique=False,
        )
    if "ix_professional_leads_status" not in idx_names:
        op.create_index(
            "ix_professional_leads_status",
            "professional_leads",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    # Keep corrective migration non-destructive on downgrade.
    pass
