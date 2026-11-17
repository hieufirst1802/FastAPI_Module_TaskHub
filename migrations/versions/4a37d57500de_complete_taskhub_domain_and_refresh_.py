"""complete taskhub domain and refresh tokens

Revision ID: 4a37d57500de
Revises: fdaf932d4a5a
Create Date: 2026-11-17 17:10:39.754173

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a37d57500de"
down_revision: str | Sequence[str] | None = "fdaf932d4a5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema, preserving standalone legacy tasks."""
    recreate = "always" if op.get_bind().dialect.name == "sqlite" else "auto"
    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_refresh_tokens_user_id"), ["user_id"], unique=False)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_workspaces_owner_id"), ["owner_id"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_project_status"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_projects_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.CheckConstraint("role IN ('OWNER','EDITOR','VIEWER')", name="ck_member_role"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_label_project_name"),
    )
    with op.batch_alter_table("labels", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_labels_project_id"), ["project_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_comments_author_id"), ["author_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_comments_task_id"), ["task_id"], unique=False)

    op.create_table(
        "task_labels",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["label_id"],
            ["labels.id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("task_id", "label_id"),
    )
    with op.batch_alter_table("tasks", schema=None, recreate=recreate) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assignee_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), server_default="TODO", nullable=False)
        )
        batch_op.add_column(
            sa.Column("priority", sa.String(length=10), server_default="MEDIUM", nullable=False)
        )
        batch_op.add_column(sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_task_status", "status IN ('TODO','IN_PROGRESS','IN_REVIEW','DONE')"
        )
        batch_op.create_check_constraint(
            "ck_task_priority", "priority IN ('LOW','MEDIUM','HIGH','URGENT')"
        )
        batch_op.create_index(batch_op.f("ix_tasks_assignee_id"), ["assignee_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tasks_project_id"), ["project_id"], unique=False)
        batch_op.create_foreign_key("fk_tasks_assignee", "users", ["assignee_id"], ["id"])
        batch_op.create_foreign_key("fk_tasks_project", "projects", ["project_id"], ["id"])

    with op.batch_alter_table("users", schema=None, recreate=recreate) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=254), nullable=True))
        batch_op.add_column(
            sa.Column("full_name", sa.String(length=200), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            )
        )
        batch_op.create_unique_constraint("uq_users_email", ["email"])

    op.execute("UPDATE tasks SET status = 'DONE' WHERE completed = true")


def downgrade() -> None:
    """Downgrade schema (workspace domain data is removed)."""
    recreate = "always" if op.get_bind().dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("users", schema=None, recreate=recreate) as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("created_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("full_name")
        batch_op.drop_column("email")

    with op.batch_alter_table("tasks", schema=None, recreate=recreate) as batch_op:
        batch_op.drop_constraint("fk_tasks_project", type_="foreignkey")
        batch_op.drop_constraint("fk_tasks_assignee", type_="foreignkey")
        batch_op.drop_constraint("ck_task_status", type_="check")
        batch_op.drop_constraint("ck_task_priority", type_="check")
        batch_op.drop_index(batch_op.f("ix_tasks_project_id"))
        batch_op.drop_index(batch_op.f("ix_tasks_assignee_id"))
        batch_op.drop_column("created_at")
        batch_op.drop_column("due_date")
        batch_op.drop_column("priority")
        batch_op.drop_column("status")
        batch_op.drop_column("assignee_id")
        batch_op.drop_column("project_id")

    op.drop_table("task_labels")
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_comments_task_id"))
        batch_op.drop_index(batch_op.f("ix_comments_author_id"))

    op.drop_table("comments")
    with op.batch_alter_table("labels", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_labels_project_id"))

    op.drop_table("labels")
    op.drop_table("workspace_members")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_workspace_id"))

    op.drop_table("projects")
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_workspaces_owner_id"))

    op.drop_table("workspaces")
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_user_id"))

    op.drop_table("refresh_tokens")
