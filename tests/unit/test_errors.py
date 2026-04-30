"""US-002: CLIError subclasses map to deterministic exit codes."""

from __future__ import annotations

from notion_cli.errors import APIError, AuthError, CLIError, NotFoundError, UserError


def test_cli_error_defaults() -> None:
    err = CLIError("boom")
    assert err.message == "boom"
    assert err.hint is None
    assert err.exit_code == 1
    assert err.code == "ERROR"


def test_user_error_exit_code() -> None:
    assert UserError("x").exit_code == 1
    assert UserError("x").code == "USER_ERROR"


def test_auth_error_exit_code() -> None:
    assert AuthError("x").exit_code == 2
    assert AuthError("x").code == "AUTH_ERROR"


def test_api_error_exit_code() -> None:
    assert APIError("x").exit_code == 3
    assert APIError("x").code == "API_ERROR"


def test_not_found_exit_code() -> None:
    assert NotFoundError("x").exit_code == 4
    assert NotFoundError("x").code == "NOT_FOUND"


def test_hint_is_carried() -> None:
    err = AuthError("invalid", hint="run init")
    assert err.hint == "run init"
