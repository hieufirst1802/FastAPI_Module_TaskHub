"""Constrain system roles to the values defined in UserRole."""

from alembic import op

revision = "84263bf18d02"
down_revision = "4a37d57500de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = lower(role) WHERE lower(role) IN ('admin', 'member')")
    with op.batch_alter_table("users") as batch:
        batch.create_check_constraint("ck_users_role", "role IN ('admin', 'member')")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
