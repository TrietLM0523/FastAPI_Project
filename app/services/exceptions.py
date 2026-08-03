class ServiceError(Exception):
    """Base error raised by the service layer."""


class AuthenticationError(ServiceError):
    """Credentials are invalid."""


class ConflictError(ServiceError):
    """A unique resource already exists."""


class ForbiddenError(ServiceError):
    """The actor does not have permission for an operation."""


class InactiveUserError(ServiceError):
    """The account is disabled."""


class NotFoundError(ServiceError):
    """The requested resource does not exist."""
