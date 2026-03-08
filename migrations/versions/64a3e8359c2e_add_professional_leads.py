"""add professional leads

Revision ID: 64a3e8359c2e
Revises: magic_link_tokens
Create Date: 2026-02-13 09:45:13.359089

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '64a3e8359c2e'
down_revision = 'magic_link_tokens'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "professional_leads" not in tables:
        op.create_table(
            "professional_leads",
            sa.Column("id", sa.Integer(), nullable=False),
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
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("professional_leads")}
    with op.batch_alter_table("professional_leads", schema=None) as batch_op:
        if batch_op.f("ix_professional_leads_city") not in indexes:
            batch_op.create_index(batch_op.f("ix_professional_leads_city"), ["city"], unique=False)
        if batch_op.f("ix_professional_leads_email") not in indexes:
            batch_op.create_index(batch_op.f("ix_professional_leads_email"), ["email"], unique=False)
        if batch_op.f("ix_professional_leads_profession") not in indexes:
            batch_op.create_index(
                batch_op.f("ix_professional_leads_profession"), ["profession"], unique=False
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "professional_leads" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("professional_leads")}
    with op.batch_alter_table("professional_leads", schema=None) as batch_op:
        if batch_op.f("ix_professional_leads_profession") in indexes:
            batch_op.drop_index(batch_op.f("ix_professional_leads_profession"))
        if batch_op.f("ix_professional_leads_email") in indexes:
            batch_op.drop_index(batch_op.f("ix_professional_leads_email"))
        if batch_op.f("ix_professional_leads_city") in indexes:
            batch_op.drop_index(batch_op.f("ix_professional_leads_city"))

    op.drop_table("professional_leads")
