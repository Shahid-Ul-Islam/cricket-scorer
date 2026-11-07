"""Application services: database-aware operations built on the pure engine."""


class ServiceError(ValueError):
    """A user-facing error raised by a service (bad input, wrong match state...)."""


class NotFoundError(ServiceError):
    """The requested record does not exist."""
