"""professional leads status notes contacted_at

Revision ID: 3aa54113845d
Revises: 64a3e8359c2e
Create Date: 2026-02-13 10:55:13.979315

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3aa54113845d'
down_revision = '64a3e8359c2e'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("professional_leads")}

    if "status" not in cols:
        op.add_column(
            "professional_leads",
            sa.Column("status", sa.String(length=30), nullable=True),
        )
    if "notes" not in cols:
        op.add_column(
            "professional_leads",
            sa.Column("notes", sa.Text(), nullable=True),
        )
    if "contacted_at" not in cols:
        op.add_column(
            "professional_leads",
            sa.Column("contacted_at", sa.DateTime(), nullable=True),
        )

    op.execute("UPDATE professional_leads SET status='new' WHERE status IS NULL")

    # Enforce NOT NULL when column is still nullable.
    cols = {c["name"]: c for c in sa.inspect(bind).get_columns("professional_leads")}
    if cols.get("status", {}).get("nullable", True):
        with op.batch_alter_table("professional_leads", schema=None) as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.String(length=30),
                nullable=False,
            )

    existing_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("professional_leads")}
    if "ix_professional_leads_status" not in existing_indexes:
        op.create_index(
            "ix_professional_leads_status",
            "professional_leads",
            ["status"],
        )


def downgrade():
    op.drop_index("ix_professional_leads_status", table_name="professional_leads")
    op.drop_column("professional_leads", "contacted_at")
    op.drop_column("professional_leads", "notes")
    op.drop_column("professional_leads", "status")
