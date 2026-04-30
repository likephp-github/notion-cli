"""`notion-cli comment add / list`."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Annotated, Any, ParamSpec, TypeVar

import typer

from notion_cli import client as client_module
from notion_cli.errors import CLIError
from notion_cli.output import emit_error, emit_ok

app = typer.Typer(name="comment", help="Read and write Notion page comments.", no_args_is_help=True)

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


def _rich_to_text(rich: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for r in rich:
        if "plain_text" in r:
            out.append(str(r["plain_text"]))
        elif isinstance(r.get("text"), dict):
            out.append(str(r["text"].get("content", "")))
    return "".join(out)


@app.command("add", help="Add a comment to a card or page.")
def cmd_add(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
    text: Annotated[str, typer.Option("--text", help="Comment body.")],
) -> None:
    @_handle
    def _run() -> None:
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        comment = client_module.call(
            client.comments.create,
            parent={"page_id": card_id},
            rich_text=[{"type": "text", "text": {"content": text}}],
        )
        emit_ok(
            {
                "id": comment.get("id"),
                "created_time": comment.get("created_time"),
                "text": _rich_to_text(comment.get("rich_text", [])),
            }
        )

    _run()


@app.command("list", help="List comments on a card or page.")
def cmd_list(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
) -> None:
    @_handle
    def _run() -> None:
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        comments: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"block_id": card_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = client_module.call(client.comments.list, **kwargs)
            for c in response.get("results", []):
                comments.append(
                    {
                        "id": c.get("id"),
                        "created_time": c.get("created_time"),
                        "text": _rich_to_text(c.get("rich_text", [])),
                    }
                )
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        emit_ok({"comments": comments, "count": len(comments)})

    _run()
