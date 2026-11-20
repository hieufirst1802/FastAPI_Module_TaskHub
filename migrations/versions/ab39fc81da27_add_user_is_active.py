"""Add account activation and disable legacy demo accounts."""

import sqlalchemy as sa
from alembic import op

revision = "ab39fc81da27"
down_revision = "6efbd1a2c410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    users = sa.table("users", sa.column("password_hash"), sa.column("is_active", sa.Boolean()))
    op.execute(
        users.update().where(users.c.password_hash == "disabled-login").values(is_active=False)
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
