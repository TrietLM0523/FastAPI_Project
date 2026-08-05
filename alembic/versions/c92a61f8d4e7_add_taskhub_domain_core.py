"""add TaskHub domain core

Revision ID: c92a61f8d4e7
Revises: b7f2d91c8a44
Create Date: 2026-08-05

Legacy strategy: preserve every Day 5 task. Each distinct task owner receives a
legacy workspace, OWNER membership, and legacy project. Task ownership maps to
created_by and completed maps to TODO/DONE.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c92a61f8d4e7"
down_revision: str | Sequence[str] | None = "b7f2d91c8a44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_domain_tables() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_workspaces_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('OWNER', 'EDITOR', 'VIEWER')",
            name="ck_workspace_members_workspace_role",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_workspace_members_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_members_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id", name="pk_workspace_members"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=8), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="ck_projects_project_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )


def _create_taskhub_task_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "status", sa.String(length=11), server_default="TODO", nullable=False
        ),
        sa.Column(
            "priority", sa.String(length=6), server_default="MEDIUM", nullable=False
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE')",
            name="ck_tasks_task_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_tasks_task_priority",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name="fk_tasks_assignee_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_tasks_created_by_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_tasks_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )


def upgrade() -> None:
    _create_domain_tables()
    _create_taskhub_task_table("tasks_day6")

    connection = op.get_bind()
    owner_ids = connection.execute(
        sa.text("SELECT DISTINCT owner_id FROM tasks ORDER BY owner_id")
    ).scalars()
    for owner_id in owner_ids:
        workspace_result = connection.execute(
            sa.text(
                "INSERT INTO workspaces (name, owner_id) VALUES (:name, :owner_id)"
            ),
            {"name": f"Legacy Workspace {owner_id}", "owner_id": owner_id},
        )
        workspace_id = workspace_result.lastrowid
        connection.execute(
            sa.text(
                "INSERT INTO workspace_members (workspace_id, user_id, role) "
                "VALUES (:workspace_id, :user_id, 'OWNER')"
            ),
            {"workspace_id": workspace_id, "user_id": owner_id},
        )
        project_result = connection.execute(
            sa.text(
                "INSERT INTO projects (workspace_id, name, description, status) "
                "VALUES (:workspace_id, 'Legacy Tasks', "
                "'Migrated from the Day 5 task model', 'ACTIVE')"
            ),
            {"workspace_id": workspace_id},
        )
        project_id = project_result.lastrowid
        connection.execute(
            sa.text(
                "INSERT INTO tasks_day6 "
                "(id, project_id, assignee_id, title, description, status, "
                "priority, due_date, created_by, created_at, updated_at) "
                "SELECT id, :project_id, NULL, title, description, "
                "CASE WHEN is_completed = 1 THEN 'DONE' ELSE 'TODO' END, "
                "'MEDIUM', NULL, owner_id, created_at, updated_at "
                "FROM tasks WHERE owner_id = :owner_id"
            ),
            {"project_id": project_id, "owner_id": owner_id},
        )

    op.drop_table("tasks")
    op.rename_table("tasks_day6", "tasks")
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_index("ix_tasks_created_by", "tasks", ["created_by"])


def downgrade() -> None:
    op.create_table(
        "tasks_day5",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "is_completed", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_tasks_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO tasks_day5 "
            "(id, title, description, is_completed, owner_id, created_at, updated_at) "
            "SELECT id, title, description, "
            "CASE WHEN status = 'DONE' THEN 1 ELSE 0 END, "
            "created_by, created_at, updated_at FROM tasks"
        )
    )
    op.drop_table("tasks")
    op.rename_table("tasks_day5", "tasks")
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])

    op.drop_table("refresh_tokens")
    op.drop_table("projects")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
