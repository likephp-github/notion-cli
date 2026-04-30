"""CLI error hierarchy with exit-code mapping."""

from __future__ import annotations


class CLIError(Exception):
    """Base class for any error the CLI surfaces with a JSON envelope."""

    exit_code: int = 1
    code: str = "ERROR"

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UserError(CLIError):
    """Bad user input or local state — not the API's fault."""

    exit_code = 1
    code = "USER_ERROR"


class AuthError(CLIError):
    """Missing / invalid Notion token, or integration permission problem."""

    exit_code = 2
    code = "AUTH_ERROR"


class APIError(CLIError):
    """Notion API returned an unrecoverable error after retries."""

    exit_code = 3
    code = "API_ERROR"


class NotFoundError(CLIError):
    """The requested Notion resource (page / database / block / comment) does not exist."""

    exit_code = 4
    code = "NOT_FOUND"
