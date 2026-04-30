"""`notion-cli card list / get / create / update / archive`."""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Callable
from typing import Annotated, Any, ParamSpec, TypeVar

import typer

from notion_cli import client as client_module
from notion_cli import config as config_module
from notion_cli.errors import CLIError, UserError
from notion_cli.notion import coercion, markdown
from notion_cli.notion import schema as schema_module
from notion_cli.output import emit_error, emit_ok

app = typer.Typer(name="card", help="Operate on database cards.", no_args_is_help=True)

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


def _resolve_db(alias_or_id: str | None) -> str:
    cfg = config_module.load_config()
    db = config_module.resolve_database(alias_or_id, cfg)
    if not db:
        raise UserError(
            "No database specified.",
            hint="Pass --database <alias|id>, set NOTION_DATABASE_ID, or run `notion-cli database add`.",
        )
    return db


def _extract_title(properties: dict[str, Any]) -> str:
    for _, prop in properties.items():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return ""


def _parse_set(kv: str) -> tuple[str, str]:
    if "=" not in kv:
        raise UserError(
            f"--set expects PROPERTY=VALUE, got: {kv!r}",
            hint="Example: --set Status=Done",
        )
    prop, val = kv.split("=", 1)
    prop = prop.strip()
    if not prop:
        raise UserError(f"--set property name is empty: {kv!r}")
    return prop, val


def _build_payload(
    title: str | None,
    set_pairs: list[str],
    set_raw: str | None,
    schema_props: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a Notion properties payload, using schema-aware coercion when available.

    `schema_props` is None when the caller has only `--set-raw` (no schema needed).
    """
    payload: dict[str, Any] = {}
    if (title is not None or set_pairs) and schema_props is None:
        raise UserError("Internal: schema required for --title / --set but not provided.")

    if title is not None:
        assert schema_props is not None
        title_prop = coercion.find_title_property(schema_props)
        payload[title_prop] = coercion.coerce(title_prop, title, schema_props)

    for kv in set_pairs:
        prop, val = _parse_set(kv)
        assert schema_props is not None
        payload[prop] = coercion.coerce(prop, val, schema_props)

    if set_raw:
        try:
            raw = json.loads(set_raw)
        except json.JSONDecodeError as exc:
            raise UserError(f"--set-raw is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise UserError("--set-raw must be a JSON object mapping property name → payload.")
        payload.update(raw)
    return payload


@app.command("list", help="Query a database for cards.")
def cmd_list(
    ctx: typer.Context,
    database: Annotated[
        str | None,
        typer.Option("--database", help="Alias or id; defaults to config."),
    ] = None,
    filter_json: Annotated[
        str | None,
        typer.Option("--filter-json", help="Raw Notion filter object as JSON."),
    ] = None,
    sort: Annotated[
        str | None,
        typer.Option(
            "--sort",
            help="Comma-separated sort keys; prefix '-' for descending (e.g. '-CreatedAt').",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Max rows across pagination.", min=1, max=10_000),
    ] = 100,
) -> None:
    @_handle
    def _run() -> None:
        db_id = _resolve_db(database)
        token = (ctx.obj or {}).get("token") if ctx.obj else None

        filter_obj: dict[str, Any] | None = None
        if filter_json:
            try:
                parsed = json.loads(filter_json)
            except json.JSONDecodeError as exc:
                raise UserError(f"--filter-json is not valid JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise UserError("--filter-json must be a JSON object.")
            filter_obj = parsed

        sorts: list[dict[str, str]] = []
        if sort:
            for raw in sort.split(","):
                key = raw.strip()
                if not key:
                    continue
                if key.startswith("-"):
                    sorts.append({"property": key[1:], "direction": "descending"})
                else:
                    sorts.append({"property": key, "direction": "ascending"})

        client = client_module.get_client(token)
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(results) < limit:
            page_size = min(100, limit - len(results))
            kwargs: dict[str, Any] = {"database_id": db_id, "page_size": page_size}
            if filter_obj is not None:
                kwargs["filter"] = filter_obj
            if sorts:
                kwargs["sorts"] = sorts
            if cursor:
                kwargs["start_cursor"] = cursor

            response = client_module.call(
                client.databases.query,  # type: ignore[attr-defined]
                **kwargs,
            )
            for page in response.get("results", []):
                results.append(
                    {
                        "id": page["id"],
                        "url": page.get("url"),
                        "title": _extract_title(page.get("properties", {})),
                        "properties": page.get("properties", {}),
                        "archived": page.get("archived", False),
                    }
                )
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        truncated = results[:limit]
        emit_ok({"results": truncated, "count": len(truncated)})

    _run()


@app.command("get", help="Fetch a single card by id.")
def cmd_get(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
) -> None:
    @_handle
    def _run() -> None:
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        page = client_module.call(client.pages.retrieve, page_id=card_id)
        emit_ok(
            {
                "id": page["id"],
                "url": page.get("url"),
                "title": _extract_title(page.get("properties", {})),
                "properties": page.get("properties", {}),
                "archived": page.get("archived", False),
            }
        )

    _run()


@app.command("create", help="Create a new card in a database.")
def cmd_create(
    ctx: typer.Context,
    database: Annotated[
        str | None,
        typer.Option("--database", help="Alias or id of the target database."),
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Title for the new card.")
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Property assignment; repeat for multiple."),
    ] = None,
    set_raw: Annotated[
        str | None,
        typer.Option("--set-raw", help="Raw JSON properties object; merged after --set."),
    ] = None,
) -> None:
    @_handle
    def _run() -> None:
        if title is None and not set_ and not set_raw:
            raise UserError(
                "Nothing to set.",
                hint="Pass --title, one or more --set Prop=Value, or --set-raw '{...}'",
            )
        db_id = _resolve_db(database)
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)

        schema_props: dict[str, Any] | None = None
        if title is not None or set_:
            schema = schema_module.get_schema(client, db_id)
            schema_props = schema.get("properties", {})

        payload = _build_payload(title, set_ or [], set_raw, schema_props)
        page = client_module.call(
            client.pages.create,
            parent={"database_id": db_id},
            properties=payload,
        )
        emit_ok(
            {
                "id": page["id"],
                "url": page.get("url"),
                "title": _extract_title(page.get("properties", {})),
            }
        )

    _run()


@app.command("update", help="Update properties on an existing card.")
def cmd_update(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
    title: Annotated[
        str | None, typer.Option("--title", help="New title.")
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Property assignment; repeat for multiple."),
    ] = None,
    set_raw: Annotated[
        str | None,
        typer.Option("--set-raw", help="Raw JSON properties object; merged after --set."),
    ] = None,
) -> None:
    @_handle
    def _run() -> None:
        if title is None and not set_ and not set_raw:
            raise UserError("Nothing to update.")
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)

        schema_props: dict[str, Any] | None = None
        if title is not None or set_:
            page = client_module.call(client.pages.retrieve, page_id=card_id)
            parent = page.get("parent") or {}
            if parent.get("type") != "database_id":
                raise UserError(
                    "Cannot --title or --set on a non-database page.",
                    hint="Use --set-raw for non-database pages.",
                )
            db_id = parent["database_id"]
            schema = schema_module.get_schema(client, db_id)
            schema_props = schema.get("properties", {})

        payload = _build_payload(title, set_ or [], set_raw, schema_props)
        result = client_module.call(client.pages.update, page_id=card_id, properties=payload)
        emit_ok(
            {
                "id": result["id"],
                "url": result.get("url"),
                "properties": result.get("properties", {}),
            }
        )

    _run()


@app.command("read", help="Read card body as markdown (default) or raw blocks JSON.")
def cmd_read(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
    fmt: Annotated[
        str,
        typer.Option("--format", help="Output format: markdown or json.", case_sensitive=False),
    ] = "markdown",
) -> None:
    @_handle
    def _run() -> None:
        if fmt.lower() not in ("markdown", "json"):
            raise UserError(
                f"--format must be 'markdown' or 'json', got: {fmt!r}",
            )
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"block_id": card_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = client_module.call(client.blocks.children.list, **kwargs)
            blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        if fmt.lower() == "json":
            emit_ok({"id": card_id, "blocks": blocks})
        else:
            emit_ok({"id": card_id, "markdown": markdown.blocks_to_markdown(blocks)})

    _run()


@app.command("append", help="Append markdown content to a card.")
def cmd_append(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
    md: Annotated[
        str | None, typer.Option("--markdown", help="Markdown content to append.")
    ] = None,
    from_file: Annotated[
        str | None,
        typer.Option("--from-file", help="Read markdown from a file path."),
    ] = None,
) -> None:
    @_handle
    def _run() -> None:
        if (md is None) == (from_file is None):
            raise UserError(
                "Pass exactly one of --markdown or --from-file.",
            )
        if from_file is not None:
            try:
                with open(from_file, encoding="utf-8") as fp:
                    text = fp.read()
            except FileNotFoundError as exc:
                raise UserError(f"File not found: {from_file}") from exc
        else:
            assert md is not None
            text = md

        blocks = markdown.markdown_to_blocks(text)
        if not blocks:
            raise UserError("Markdown produced no blocks (empty or whitespace only).")

        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        client_module.call(
            client.blocks.children.append, block_id=card_id, children=blocks
        )
        emit_ok({"id": card_id, "appended": len(blocks)})

    _run()


@app.command("archive", help="Archive a card. Requires --yes (or NOTION_CLI_FORCE=1).")
def cmd_archive(
    ctx: typer.Context,
    card_id: Annotated[str, typer.Argument(help="Notion page id.")],
    yes: Annotated[
        bool, typer.Option("--yes", help="Confirm the archive (irreversible via CLI).")
    ] = False,
) -> None:
    @_handle
    def _run() -> None:
        forced = yes or os.environ.get("NOTION_CLI_FORCE") == "1"
        if not forced:
            raise UserError(
                "Archiving is irreversible from the CLI; pass --yes to confirm.",
                hint="To unarchive, restore the page in Notion's UI.",
            )
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        page = client_module.call(client.pages.retrieve, page_id=card_id)

        if page.get("archived"):
            emit_ok({"id": card_id, "archived": True, "already": True})
            return

        result = client_module.call(client.pages.update, page_id=card_id, archived=True)
        emit_ok({"id": result["id"], "archived": result.get("archived", True), "already": False})

    _run()
