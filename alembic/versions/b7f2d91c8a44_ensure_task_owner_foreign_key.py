"""ensure task owner foreign key on SQLite

Revision ID: b7f2d91c8a44
Revises: a31d6c2f4e10
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7f2d91c8a44"
down_revision: str | Sequence[str] | None = "a31d6c2f4e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    foreign_keys = sa.inspect(connection).get_foreign_keys("tasks")
    has_owner_foreign_key = any(
        foreign_key["constrained_columns"] == ["owner_id"]
        and foreign_key["referred_table"] == "users"
        for foreign_key in foreign_keys
    )

    if not has_owner_foreign_key:
        with op.batch_alter_table("tasks", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_tasks_owner_id_users",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("tasks")
    owner_foreign_key = next(
        (
            foreign_key
            for foreign_key in foreign_keys
            if foreign_key["constrained_columns"] == ["owner_id"]
            and foreign_key["referred_table"] == "users"
        ),
        None,
    )

    if owner_foreign_key is not None:
        with op.batch_alter_table("tasks", recreate="always") as batch_op:
            batch_op.drop_constraint(
                owner_foreign_key["name"],
                type_="foreignkey",
            )
