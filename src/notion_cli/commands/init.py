"""`notion-cli init` — interactive + non-interactive setup wizard."""

from __future__ import annotations

import getpass
import sys
from typing import Annotated, Any

import typer

from notion_cli import client as client_module
from notion_cli import config as config_module
from notion_cli import credentials
from notion_cli.errors import AuthError, UserError
from notion_cli.output import emit_error, emit_ok

INTEGRATIONS_URL = "https://www.notion.so/profile/integrations"


def _collect_databases(client: Any) -> list[dict[str, str]]:
    """Search for databases visible to the integration."""
    response = client_module.call(
        client.search,
        filter={"value": "database", "property": "object"},
        page_size=100,
    )
    out: list[dict[str, str]] = []
    for item in response.get("results", []):
        if item.get("object") != "database":
            continue
        title_parts = item.get("title") or []
        title = "".join(part.get("plain_text", "") for part in title_parts) or "(untitled)"
        out.append({"id": item["id"], "title": title})
    return out


def _verify_token(token: str) -> dict[str, Any]:
    client = client_module.get_client(token)
    me = client_module.call(client.users.me)
    databases = _collect_databases(client)
    bot = me.get("bot") or {}
    workspace_name = bot.get("workspace_name")
    return {
        "integration_name": me.get("name") or workspace_name or "(unnamed)",
        "bot_id": me.get("id"),
        "databases": databases,
    }


def _persist(
    token: str,
    default_db: str | None,
    alias: str | None,
) -> None:
    credentials.set_token(token)
    cfg: dict[str, Any] = config_module.load_config()
    if default_db:
        cfg.setdefault("default", {})["database"] = default_db
        if alias:
            databases = cfg.setdefault("databases", {})
            databases[alias] = {"id": default_db}
    config_module.save_config(cfg)


def cmd_init(
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            help="Notion Internal Integration token. Hidden prompt when omitted in a TTY.",
        ),
    ] = None,
    database: Annotated[
        str | None,
        typer.Option("--database", help="Default Notion database id."),
    ] = None,
    alias: Annotated[
        str | None,
        typer.Option("--alias", help="Alias for the default database (e.g. 'requirements')."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing credentials and config."),
    ] = False,
) -> None:
    """Set up the CLI for a Notion workspace (token + default database)."""
    existing_source = credentials.token_source()
    if existing_source and not force:
        emit_error(
            "ALREADY_CONFIGURED",
            f"Credentials already present (source={existing_source}).",
            hint="Re-run with --force to overwrite, or `notion-cli logout` first.",
        )
        raise typer.Exit(1)

    interactive = token is None
    if interactive and not sys.stdin.isatty():
        emit_error(
            "NO_TTY",
            "Cannot prompt for a token when stdin is not a TTY.",
            hint=f"Pass --token, or run interactively. Create a token at {INTEGRATIONS_URL}.",
        )
        raise typer.Exit(1)

    if interactive:
        sys.stderr.write(
            f"Create or open an Internal Integration here:\n  {INTEGRATIONS_URL}\n"
            "Paste the token below (input is hidden):\n"
        )
        token = getpass.getpass(prompt="Notion token: ").strip()
        if not token:
            raise UserError("Empty token.", hint=f"Generate a token at {INTEGRATIONS_URL}.")

    assert token is not None  # narrowed by interactive prompt or non-interactive flag
    try:
        info = _verify_token(token)
    except AuthError as exc:
        emit_error("INVALID_TOKEN", exc.message, hint=exc.hint)
        raise typer.Exit(2) from exc

    chosen_db = database
    if interactive and not chosen_db:
        chosen_db, alias = _prompt_database(info["databases"], alias)

    _persist(token, chosen_db, alias)

    emit_ok(
        {
            "integration_name": info["integration_name"],
            "bot_id": info["bot_id"],
            "default_database": chosen_db,
            "alias": alias,
            "token_source": credentials.token_source(),
            "databases_visible": [db["id"] for db in info["databases"]],
        }
    )


def _prompt_database(
    databases: list[dict[str, str]], alias: str | None
) -> tuple[str | None, str | None]:
    if not databases:
        sys.stderr.write(
            "No databases are visible to this integration yet.\n"
            "Open the database page in Notion → ⋯ menu → 'Add connections' → choose this integration.\n"
            "You can re-run `notion-cli init --force` later, or use `notion-cli database add`.\n"
        )
        return None, alias

    sys.stderr.write("\nDatabases visible to this integration:\n")
    for idx, db in enumerate(databases, 1):
        sys.stderr.write(f"  [{idx}] {db['title']}  ({db['id']})\n")
    sys.stderr.write("  [s] Skip — set later\n")

    while True:
        choice = input("Pick a default database: ").strip().lower()
        if choice == "s":
            return None, alias
        if choice.isdigit() and 1 <= int(choice) <= len(databases):
            picked = databases[int(choice) - 1]
            if alias is None:
                supplied = input("Alias (blank to skip): ").strip()
                alias = supplied or None
            return picked["id"], alias
        sys.stderr.write("Please enter a number from the list, or 's' to skip.\n")
