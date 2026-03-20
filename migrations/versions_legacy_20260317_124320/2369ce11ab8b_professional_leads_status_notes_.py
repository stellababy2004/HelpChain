"""professional leads status notes contacted_at

Revision ID: 2369ce11ab8b
Revises: 3aa54113845d
Create Date: 2026-02-13 11:02:58.923774

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2369ce11ab8b'
down_revision = '3aa54113845d'
branch_labels = None
depends_on = None


def upgrade():
    # Keep the most recent lead per email before enforcing uniqueness.
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