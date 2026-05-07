"""Domain errors (no HTTP): map to status codes at the delivery layer."""


class DomainError(Exception):
    """Base for business-rule failures."""


class ProjectNotFound(DomainError):
    pass
