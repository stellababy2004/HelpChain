"""ensure structures table and default tenant seed exist

Revision ID: 6e8a1b4c9d20
Revises: 5f4e3d2c1b0a
Create Date: 2026-03-11 10:03:00
"""

from alembic import op
import sqlalchemy as sa


revision = "6e8a1b4c9d20"
down_revision = "5f4e3d2c1b0a"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def _fk_names(bind, table_name: str) -> set[str]:
    names = set()
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return names
    for fk in insp.get_foreign_keys(table_name):
        name = fk.get("name")
        if name:
            names.add(name)
    return names


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "structures"):
        op.create_table(
            "structures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    row = bind.execute(
        sa.text("SELECT id FROM structures WHERE slug = :slug LIMIT 1"),
        {"slug": "default"},
    ).fetchone()
    if not row:
        bind.execute(
            sa.text(
                """
                INSERT INTO structures (name, slug, created_at)
                VALUES (:name, :slug, :created_at)
                """
            ),
            {
                "name": "Default",
                "slug": "default",
                "created_at": "2026-01-01 00:00:00",
            },
        )

    # Keep compatibility for DBs where requests exists but FK was never created.
    if _table_exists(bind, "requests"):
        default_id = bind.execute(
            sa.text("SELECT id FROM structures WHERE slug = :slug LIMIT 1"),
            {"slug": "default"},
        ).scalar()
        if default_id is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE requests
                    SET structure_id = :default_id
                    WHERE structure_id IS NULL
                    """
                ),
                {"default_id": int(default_id)},
            )

        if bind.dialect.name != "sqlite":
            fk_name = "fk_requests_structure_id"
            if fk_name not in _fk_names(bind, "requests"):
                op.create_foreign_key(
                    fk_name,
                    "requests",
                    "structures",
                    ["structure_id"],
                    ["id"],
                )


def downgrade() -> None:
    # Intentionally no-op to avoid destructive table drops in shared environments.
    pass