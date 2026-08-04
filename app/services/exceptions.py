class ServiceError(Exception):
    """Base error raised by the service layer."""

    default_message = "Service error"
    default_error_code = "service_error"

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.error_code = error_code or self.default_error_code
        super().__init__(self.message)


class AuthenticationError(ServiceError):
    """Credentials are invalid."""

    default_message = "Incorrect email or password"
    default_error_code = "authentication"


class ConflictError(ServiceError):
    """A unique resource already exists."""

    default_message = "Resource already exists"
    default_error_code = "conflict"


class ForbiddenError(ServiceError):
    """The actor does not have permission for an operation."""

    default_message = "Permission denied"
    default_error_code = "forbidden"


class InactiveUserError(ServiceError):
    """The account is disabled."""

    default_message = "User is inactive"
    default_error_code = "inactive_user"


class NotFoundError(ServiceError):
    """The requested resource does not exist."""

    default_message = "Resource not found"
    default_error_code = "not_found"
