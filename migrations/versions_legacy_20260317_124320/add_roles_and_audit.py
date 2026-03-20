"""placeholder base revision for older deployments

This repo snapshot referenced a missing down_revision ("add_roles_and_audit").
We keep this revision as a no-op so Alembic's revision graph is valid.
"""

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision = "add_roles_and_audit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass