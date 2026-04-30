"""Logging setup with token masking for verbose / debug output."""

from __future__ import annotations

import logging
import os
import re
import sys

_TOKEN_PATTERN = re.compile(r"(secret_|ntn_)[A-Za-z0-9_-]{6,}")


def mask_token(text: str) -> str:
    """Replace any Notion token-like substring with `secret_***`."""
    return _TOKEN_PATTERN.sub("secret_***", text)


class _MaskFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_token(record.msg)
        if record.args:
            record.args = tuple(
                mask_token(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def setup_logging(verbose: bool = False) -> None:
    """Configure the root logger to write to stderr and mask any tokens."""
    level_env = os.environ.get("NOTION_CLI_LOG", "").lower()
    if level_env == "debug":
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    handler.addFilter(_MaskFilter())

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)
