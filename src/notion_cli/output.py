"""Output contract: JSON envelopes on stdout (success) / stderr (error).

Modes:
- compact JSON (default, AI-friendly): one-line `json.dumps` with no spacing
- pretty (human-friendly, set by `--pretty` on the root command): rich-rendered
  pretty-printed and colorized JSON
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console

_PRETTY = False
_stdout_console: Console | None = None
_stderr_console: Console | None = None


def set_pretty(pretty: bool) -> None:
    """Toggle pretty (rich) output. Called from the cli root callback."""
    global _PRETTY, _stdout_console, _stderr_console
    _PRETTY = pretty
    if pretty:
        _stdout_console = Console()
        _stderr_console = Console(stderr=True)


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def emit_ok(data: Any, meta: dict[str, Any] | None = None) -> None:
    """Write a success envelope {ok: true, data, meta?} to stdout."""
    payload: dict[str, Any] = {"ok": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    if _PRETTY and _stdout_console is not None:
        _stdout_console.print_json(data=payload)
    else:
        sys.stdout.write(_dump(payload) + "\n")
        sys.stdout.flush()


def emit_error(code: str, message: str, hint: str | None = None) -> None:
    """Write an error envelope {ok: false, error: {...}} to stderr."""
    err: dict[str, Any] = {"code": code, "message": message}
    if hint is not None:
        err["hint"] = hint
    payload: dict[str, Any] = {"ok": False, "error": err}
    if _PRETTY and _stderr_console is not None:
        _stderr_console.print_json(data=payload)
    else:
        sys.stderr.write(_dump(payload) + "\n")
        sys.stderr.flush()
