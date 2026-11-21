"""Add task status, user roles, cascade deletes and a demo owner."""

import sqlalchemy as sa
from alembic import op

revision = "6efbd1a2c410"
down_revision = "fdaf932d4a5a"
branch_labels = None
depends_on = None

TASK_STATUS = sa.Enum(
    "TODO",
    "IN_PROGRESS",
    "DONE",
    name="task_status",
    native_enum=False,
)
USER_ROLE = sa.Enum(
    "member",
    "admin",
    name="user_role",
    native_enum=False,
)
OWNER_FK = "fk_tasks_owner_id_users"
NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}

users = sa.table("users", sa.column("username"), sa.column("password_hash"), sa.column("role"))
tasks = sa.table("tasks", sa.column("completed", sa.Boolean()), sa.column("status", TASK_STATUS))


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(10), type_=USER_ROLE)
        batch.create_check_constraint("user_role", "role IN ('member', 'admin')")

    op.execute(
        users.insert().from_select(
            ["username", "password_hash", "role"],
            sa.select(sa.literal("demo"), sa.literal("disabled-login"), sa.literal("member")).where(
                ~sa.exists(sa.select(1).where(users.c.username == "demo"))
            ),
        )
    )

    op.add_column("tasks", sa.Column("status", TASK_STATUS, nullable=True))
    op.execute(tasks.update().values(status=sa.case((tasks.c.completed, "DONE"), else_="TODO")))

    with op.batch_alter_table("tasks", naming_convention=NAMING_CONVENTION) as batch:
        batch.alter_column("status", existing_type=TASK_STATUS, nullable=False)
        batch.create_check_constraint("task_status", "status IN ('TODO', 'IN_PROGRESS', 'DONE')")
        batch.drop_column("completed")
        if op.get_context().dialect.name == "sqlite":
            batch.drop_constraint(OWNER_FK, type_="foreignkey")
        else:
            existing_fk = sa.inspect(op.get_bind()).get_foreign_keys("tasks")
            owner_fk = next(
                fk["name"] for fk in existing_fk if fk["constrained_columns"] == ["owner_id"]
            )
            batch.drop_constraint(owner_fk, type_="foreignkey")
        batch.create_foreign_key(OWNER_FK, "users", ["owner_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.add_column("tasks", sa.Column("completed", sa.Boolean(), nullable=True))
    op.execute(tasks.update().values(completed=tasks.c.status == "DONE"))

    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("task_status", type_="check")
        batch.drop_column("status")
        batch.alter_column("completed", existing_type=sa.Boolean(), nullable=False)
        batch.drop_constraint(OWNER_FK, type_="foreignkey")
        batch.create_foreign_key(OWNER_FK, "users", ["owner_id"], ["id"])

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("user_role", type_="check")
        batch.alter_column("role", existing_type=USER_ROLE, type_=sa.String(10))
