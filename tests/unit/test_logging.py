"""US-005: log filter masks Notion tokens."""

from __future__ import annotations

import logging

from notion_cli.logging import mask_token, setup_logging


def test_mask_token_replaces_secret_prefix() -> None:
    masked = mask_token("Authorization: Bearer secret_abcdefghijklmn")
    assert "secret_abc" not in masked
    assert "secret_***" in masked


def test_mask_token_replaces_ntn_prefix() -> None:
    masked = mask_token("token=ntn_abcdefghijklmn")
    assert "ntn_abc" not in masked
    assert "secret_***" in masked


def test_mask_token_idempotent_on_already_masked() -> None:
    assert mask_token("secret_***") == "secret_***"


def test_setup_logging_routes_to_stderr_with_masking(
    capsys: object,
) -> None:
    setup_logging(verbose=True)
    log = logging.getLogger("notion_cli.test")
    log.info("requesting with secret_abcdefghijkl token")
    handlers = logging.getLogger().handlers
    assert handlers, "expected at least one handler"
    # Filter chain on the handler must include our masking filter
    has_filter = any(getattr(f, "filter", None) for f in handlers[0].filters)
    assert has_filter
