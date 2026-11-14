from app.core.messages import TASK_NOT_FOUND


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int,
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(
            message=TASK_NOT_FOUND,
            status_code=404,
        )
