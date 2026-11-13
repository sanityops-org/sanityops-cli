"""API exception definitions for sanityops CLI."""

from sanityops_cli.exceptions.base_exceptions import sanityopsError


class APIError(sanityopsError):
    """Base exception for API-related errors."""

    exit_code: int = 5


class AuthenticationError(APIError):
    """Authentication failed (401/403).

    The API key is invalid, expired, or lacks required permissions.
    """

    exit_code: int = 5


class ProjectNotFoundError(APIError):
    """Project not found (404).

    The specified project ID does not exist or user lacks access.
    """

    exit_code: int = 6


class NetworkError(APIError):
    """Network-related error.

    Connection timeout, DNS failure, or other network issues.
    """

    exit_code: int = 7


class ValidationError(APIError):
    """Validation error (422).

    Request parameters failed validation.
    """

    exit_code: int = 2
