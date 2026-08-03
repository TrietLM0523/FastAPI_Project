"""add RBAC fields and explicit task ownership

Revision ID: a31d6c2f4e10
Revises: 6670dfd98bf0
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a31d6c2f4e10"
down_revision: str | Sequence[str] | None = "6670dfd98bf0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    table_names = set(sa.inspect(connection).get_table_names())

    for temporary_table in ("_alembic_tmp_users", "_alembic_tmp_tasks"):
        if temporary_table in table_names:
            op.drop_table(temporary_table)

    user_columns = {
        column["name"] for column in sa.inspect(connection).get_columns("users")
    }

    if "role" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "role",
                sa.String(length=5),
                server_default="user",
                nullable=False,
            ),
        )
    if "is_active" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
        )

    inspector = sa.inspect(connection)
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}

    if "user_id" in task_columns:
        index_names = {index["name"] for index in inspector.get_indexes("tasks")}
        if "ix_tasks_user_id" in index_names:
            op.drop_index("ix_tasks_user_id", table_name="tasks")

        foreign_key_names = {
            foreign_key["name"] for foreign_key in inspector.get_foreign_keys("tasks")
        }
        with op.batch_alter_table("tasks", recreate="always") as batch_op:
            if "fk_tasks_user_id_users" in foreign_key_names:
                batch_op.drop_constraint(
                    "fk_tasks_user_id_users",
                    type_="foreignkey",
                )
            batch_op.alter_column(
                "user_id",
                new_column_name="owner_id",
                existing_type=sa.Integer(),
                existing_nullable=False,
            )
            batch_op.create_foreign_key(
                "fk_tasks_owner_id_users",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="CASCADE",
            )

        op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_index("ix_tasks_owner_id")
        batch_op.drop_constraint("fk_tasks_owner_id_users", type_="foreignkey")
        batch_op.alter_column(
            "owner_id",
            new_column_name="user_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_tasks_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_tasks_user_id", ["user_id"], unique=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("role")
