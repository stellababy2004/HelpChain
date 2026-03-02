"""ensure volunteers table has all columns used by ORM

Revision ID: e9c4b7a2d1f0
Revises: d2e8f4a1b6c3
Create Date: 2026-03-02 16:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e9c4b7a2d1f0"
down_revision = "d2e8f4a1b6c3"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {col.get("name") for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteers" not in set(inspector.get_table_names()):
        return

    cols = _column_names(inspector, "volunteers")

    desired_columns: list[tuple[str, sa.types.TypeEngine]] = [
        ("user_id", sa.Integer()),
        ("name", sa.String(length=200)),
        ("email", sa.String(length=200)),
        ("phone", sa.String(length=50)),
        ("location", sa.String(length=200)),
        ("availability", sa.String(length=50)),
        ("skills", sa.Text()),
        ("latitude", sa.Float()),
        ("longitude", sa.Float()),
        ("is_active", sa.Boolean()),
        ("volunteer_onboarded", sa.Boolean()),
        ("created_at", sa.DateTime()),
        ("updated_at", sa.DateTime()),
        ("achievements", sa.Text()),
        ("total_tasks_completed", sa.Integer()),
        ("rating", sa.Integer()),
        ("level", sa.Integer()),
        ("streak_days", sa.Integer()),
        ("rank", sa.Integer()),
        ("rating_count", sa.Integer()),
        ("total_hours_volunteered", sa.Integer()),
        ("points", sa.Integer()),
        ("experience", sa.Integer()),
        ("last_activity", sa.DateTime()),
    ]

    for name, col_type in desired_columns:
        if name not in cols:
            op.add_column("volunteers", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    # Non-destructive corrective migration.
    pass

