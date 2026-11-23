TASK_NOT_FOUND = "Task not found"
INVALID_AUTH_CREDENTIALS = "Invalid or missing authentication credentials"
INVALID_TOKEN = "Invalid access token"
INCORRECT_LOGIN = "Incorrect username or password"
USERNAME_ALREADY_REGISTERED = "Username already registered"
ACCESS_FORBIDDEN = "You do not have permission to access this resource"
REQUEST_VALIDATION_FAILED = "Request validation failed"
INTERNAL_SERVER_ERROR = "An unexpected error occurred"
NULL_UPDATE_FIELDS = "Fields cannot be null. Omit unchanged fields."
EMAIL_ALREADY_REGISTERED = "Email already registered"
INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"
INCORRECT_CURRENT_PASSWORD = "Incorrect current password"
WORKSPACE_NOT_FOUND = "Workspace not found"
INSUFFICIENT_WORKSPACE_ROLE = "Insufficient workspace role"
OWNER_ROLE_IMMUTABLE = "Workspace owner role cannot be changed"
ACTIVE_USER_NOT_FOUND = "Active user not found"
MEMBER_NOT_FOUND = "Member not found"
CANNOT_REMOVE_OWNER = "Cannot remove workspace owner"
PROJECT_NOT_FOUND = "Project not found"
PROJECT_ARCHIVED = "Project is archived"
PROJECT_TASK_NOT_FOUND = "Project task not found"
INVALID_ASSIGNEE = "Assignee must be an active workspace member"
LABEL_ALREADY_EXISTS = "Label name already exists in project"
LABEL_NOT_FOUND = "Label not found"
LABEL_PROJECT_MISMATCH = "Label and task must belong to the same project"
COMMENT_NOT_FOUND = "Comment not found"


ERROR_DESCRIPTIONS = {
    400: "The request could not be applied.",
    401: "Credentials are missing, invalid, expired, or revoked.",
    403: "The account does not have permission to perform this operation.",
    404: "The resource does not exist or is not visible to this account.",
    409: "The operation conflicts with the current state of the resource.",
    422: "The request failed field validation or a domain input rule.",
    500: "An unexpected server error occurred.",
}
