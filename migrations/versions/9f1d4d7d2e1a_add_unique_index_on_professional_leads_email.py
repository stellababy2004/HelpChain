"""add unique index on professional leads email

Revision ID: 9f1d4d7d2e1a
Revises: 2369ce11ab8b
Create Date: 2026-02-13 13:05:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9f1d4d7d2e1a"
down_revision = "2369ce11ab8b"
branch_labels = None
depends_on = None


def upgrade():
    # Compat migration note:
    # 2369ce11ab8b may already have created this index in some environments.
    # Keep this revision for history synchronization across diverged DB states.
    # Keep latest lead per normalized email before enforcing uniqueness.
    op.execute(
        """
        DELETE FROM professional_leads
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM professional_leads
            GROUP BY lower(trim(email))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_professional_leads_email "
        "ON professional_leads(email)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ux_professional_leads_email")
