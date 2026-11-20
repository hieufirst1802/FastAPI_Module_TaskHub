from enum import StrEnum


class TaskStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class UserRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"
