"""`notion-cli auth verify` and `notion-cli auth status`."""

from __future__ import annotations

from typing import Any

import typer

from notion_cli import client as client_module
from notion_cli import config as config_module
from notion_cli import credentials
from notion_cli.errors import AuthError
from notion_cli.output import emit_error, emit_ok

app = typer.Typer(name="auth", help="Verify and inspect credentials.", no_args_is_help=True)


@app.command("verify", help="Validate the active token and list visible databases.")
def cmd_verify(ctx: typer.Context) -> None:
    token = (ctx.obj or {}).get("token") if ctx.obj else None
    try:
        client = client_module.get_client(token)
        me = client_module.call(client.users.me)
        response = client_module.call(
            client.search,
            filter={"value": "database", "property": "object"},
            page_size=100,
        )
    except AuthError as exc:
        emit_error("INVALID_TOKEN", exc.message, hint=exc.hint)
        raise typer.Exit(2) from exc

    databases: list[dict[str, str]] = []
    for item in response.get("results", []):
        if item.get("object") != "database":
            continue
        title_parts = item.get("title") or []
        title = "".join(p.get("plain_text", "") for p in title_parts) or "(untitled)"
        databases.append({"id": item["id"], "title": title})

    bot = me.get("bot") or {}
    emit_ok(
        {
            "integration_name": me.get("name") or bot.get("workspace_name") or "(unnamed)",
            "bot_id": me.get("id"),
            "databases": databases,
        }
    )


@app.command("status", help="Report whether a token is configured and where it lives.")
def cmd_status() -> None:
    source = credentials.token_source()
    cfg = config_module.load_config()
    default_db: Any = None
    if isinstance(cfg.get("default"), dict):
        default_db = cfg["default"].get("database")

    emit_ok(
        {
            "configured": source is not None,
            "token_source": source,
            "config_path": str(config_module.config_path()),
            "default_database": default_db,
        }
    )
