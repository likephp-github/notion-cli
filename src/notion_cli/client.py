"""Notion API client wrapper with retry and token resolution."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError, HTTPResponseError, RequestTimeoutError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from notion_cli import credentials
from notion_cli.errors import APIError, AuthError, NotFoundError

log = logging.getLogger(__name__)


def get_client(token: str | None = None) -> Client:
    """Return an authenticated notion_client.Client.

    Token resolution: explicit argument → credentials.get_token().
    Raises AuthError when no token is available.
    """
    resolved = token or credentials.get_token()
    if not resolved:
        raise AuthError(
            "No Notion token configured.",
            hint="Run `notion-cli init` or set NOTION_TOKEN.",
        )
    return Client(auth=resolved)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RequestTimeoutError | HTTPResponseError):
        return True
    if isinstance(exc, APIResponseError):
        status = getattr(exc, "status", None)
        if status == 429 or (isinstance(status, int) and status >= 500):
            return True
    return False


_retry_decorator = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


def call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Invoke a Notion API callable with retry on transient failures.

    Returns Any because notion-client's typings widen to ``Any | Awaitable[Any]``;
    callers can index/key the dict directly.
    """

    @_retry_decorator
    def _attempt() -> Any:
        return func(*args, **kwargs)

    try:
        return _attempt()
    except APIResponseError as exc:
        status = getattr(exc, "status", None)
        code = getattr(exc, "code", None)
        message = str(exc)
        if status == 401 or code == "unauthorized":
            raise AuthError(
                "Notion rejected the token (401 unauthorized).",
                hint="Check the integration token; run `notion-cli init --force` to reset.",
            ) from exc
        if status == 404 or code == "object_not_found":
            raise NotFoundError(message, hint="Verify the id and that the integration has access.") from exc
        raise APIError(message) from exc
    except (RequestTimeoutError, HTTPResponseError) as exc:
        raise APIError(f"Network error talking to Notion: {exc}") from exc
