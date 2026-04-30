"""`notion-cli search "<query>" [--type page|database] [--limit N]`."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Annotated, Any, ParamSpec, TypeVar

import typer

from notion_cli import client as client_module
from notion_cli.errors import CLIError, UserError
from notion_cli.output import emit_error, emit_ok

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _handle(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    @functools.wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return fn(*args, **kwargs)
        except CLIError as exc:
            emit_error(exc.code, exc.message, exc.hint)
            raise typer.Exit(exc.exit_code) from exc

    return wrapper


def _extract_title(item: dict[str, Any]) -> str:
    obj = item.get("object")
    if obj == "database":
        parts = item.get("title") or []
    else:
        properties = item.get("properties") or {}
        parts = []
        for prop in properties.values():
            if prop.get("type") == "title":
                parts = prop.get("title") or []
                break
    out: list[str] = []
    for p in parts:
        if "plain_text" in p:
            out.append(str(p["plain_text"]))
        elif isinstance(p.get("text"), dict):
            out.append(str(p["text"].get("content", "")))
    return "".join(out)


def cmd_search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Free-text query.")],
    type_filter: Annotated[
        str | None,
        typer.Option("--type", help="Restrict to 'page' or 'database'."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum results across pagination.", min=1, max=10_000),
    ] = 50,
) -> None:
    @_handle
    def _run() -> None:
        if type_filter is not None and type_filter not in ("page", "database"):
            raise UserError(
                f"--type must be 'page' or 'database', got: {type_filter!r}",
            )
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(results) < limit:
            page_size = min(100, limit - len(results))
            kwargs: dict[str, Any] = {"query": query, "page_size": page_size}
            if type_filter:
                kwargs["filter"] = {"value": type_filter, "property": "object"}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = client_module.call(client.search, **kwargs)
            for item in response.get("results", []):
                results.append(
                    {
                        "id": item.get("id"),
                        "type": item.get("object"),
                        "title": _extract_title(item),
                        "url": item.get("url"),
                    }
                )
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        truncated = results[:limit]
        emit_ok({"results": truncated, "count": len(truncated)})

    _run()
