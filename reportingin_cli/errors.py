"""Error handling and exit codes for Reporting In CLI.

AIDEV-NOTE: Exit codes follow a specific scheme:
- 0: Success
- 1: Unhealthy status (for health command)
- 2-4: API/network errors
- 5: Configuration errors
- 10-11: Invalid arguments or not found
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes for the CLI.

    These codes provide meaningful feedback about command outcomes.
    In lenient mode (default for submit), all errors result in 0.
    """

    SUCCESS = 0
    ERROR_UNHEALTHY = 1  # Health check returned unhealthy status
    ERROR_API = 2  # API returned an error response
    ERROR_CONNECTION = 3  # Could not connect to the server
    ERROR_TIMEOUT = 4  # Request timed out
    ERROR_CONFIG = 5  # Configuration file error
    ERROR_INVALID_ARGS = 10  # Invalid command arguments
    ERROR_NOT_FOUND = 11  # Resource not found (group, job)


class ReportingInError(Exception):
    """Base exception for Reporting In CLI errors."""

    exit_code: ExitCode = ExitCode.ERROR_API

    def __init__(self, message: str, exit_code: ExitCode | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ConfigError(ReportingInError):
    """Configuration file error."""

    exit_code = ExitCode.ERROR_CONFIG


class ConnectionError(ReportingInError):
    """Could not connect to the server."""

    exit_code = ExitCode.ERROR_CONNECTION


class TimeoutError(ReportingInError):
    """Request timed out."""

    exit_code = ExitCode.ERROR_TIMEOUT


class ApiError(ReportingInError):
    """API returned an error response."""

    exit_code = ExitCode.ERROR_API

    def __init__(
        self, message: str, status_code: int | None = None, exit_code: ExitCode | None = None
    ) -> None:
        super().__init__(message, exit_code)
        self.status_code = status_code


class NotFoundError(ReportingInError):
    """Resource not found."""

    exit_code = ExitCode.ERROR_NOT_FOUND


class InvalidArgsError(ReportingInError):
    """Invalid command arguments."""

    exit_code = ExitCode.ERROR_INVALID_ARGS


def get_exit_code(error: Exception) -> int:
    """Map an exception to an exit code."""
    if isinstance(error, ReportingInError):
        return error.exit_code
    return ExitCode.ERROR_API
