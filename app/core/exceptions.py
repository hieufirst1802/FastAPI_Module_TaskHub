class AppException(Exception):
    """Base class for expected application errors."""

    status_code = 500
    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsernameAlreadyExistsError(AppException):
    """Raised when a registration username is already in use."""

    status_code = 409
    code = "username_already_exists"

    def __init__(self) -> None:
        super().__init__("Username already registered")
