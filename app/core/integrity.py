from sqlite3 import SQLITE_CONSTRAINT_UNIQUE
from sqlite3 import IntegrityError as SQLiteIntegrityError

from sqlalchemy.exc import IntegrityError

USERS_EMAIL_CONSTRAINT = "uq_users_email"
USERS_USERNAME_INDEX = "ix_users_username"
LABEL_NAME_CONSTRAINT = "uq_label_project_name"


def is_unique_violation(error: IntegrityError, constraint: str, columns: str) -> bool:
    original = error.orig
    if isinstance(original, SQLiteIntegrityError):
        # SQLite reports column names in place of the declared constraint name.
        return (
            original.sqlite_errorcode == SQLITE_CONSTRAINT_UNIQUE
            and str(original) == f"UNIQUE constraint failed: {columns}"
        )

    # asyncpg's driver error is attached as the cause of SQLAlchemy's adapter error.
    for source in (original, getattr(original, "__cause__", None)):
        if getattr(source, "constraint_name", None) == constraint:
            return True
        if getattr(getattr(source, "diag", None), "constraint_name", None) == constraint:
            return True
    return False
