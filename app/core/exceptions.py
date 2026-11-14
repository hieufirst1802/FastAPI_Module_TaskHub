class TaskNotFoundError(Exception):
    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
        super().__init__(f"Task {identifier} not found")