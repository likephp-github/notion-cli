"""notion-cli — Typer root application."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from notion_cli import __version__, output
from notion_cli.errors import CLIError
from notion_cli.logging import setup_logging
from notion_cli.output import emit_error

app = typer.Typer(
    name="notion-cli",
    help="AI-driven CLI for operating a Notion workspace.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        # Print version as plain text — predictable for shell scripts.
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    pretty: Annotated[
        bool,
        typer.Option("--pretty/--json", help="Human-readable tables vs JSON envelope."),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Log HTTP requests/responses to stderr.")
    ] = False,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            help="Override the stored Notion token for this invocation.",
            envvar="NOTION_TOKEN",
        ),
    ] = None,
) -> None:
    setup_logging(verbose=verbose)
    output.set_pretty(pretty)
    ctx.obj = {"pretty": pretty, "verbose": verbose, "token": token}


# Subcommand groups
from notion_cli.commands import auth as _auth_cmd  # noqa: E402
from notion_cli.commands import card as _card_cmd  # noqa: E402
from notion_cli.commands import comments as _comment_cmd  # noqa: E402
from notion_cli.commands import database as _database_cmd  # noqa: E402
from notion_cli.commands import init as _init_cmd  # noqa: E402
from notion_cli.commands import logout as _logout_cmd  # noqa: E402
from notion_cli.commands import search as _search_cmd  # noqa: E402

app.add_typer(_auth_cmd.app, name="auth", help="Verify and inspect credentials.")
app.add_typer(_database_cmd.app, name="database", help="Manage database aliases.")
app.add_typer(_card_cmd.app, name="card", help="Operate on database cards.")
app.add_typer(_comment_cmd.app, name="comment", help="Read and write Notion comments.")
app.command("init", help="Interactive setup: token + default database.")(_init_cmd.cmd_init)
app.command("logout", help="Clear stored credentials, config, and cache.")(_logout_cmd.cmd_logout)
app.command("search", help="Full-text search across the workspace.")(_search_cmd.cmd_search)


def main() -> None:
    try:
        app()
    except CLIError as exc:
        emit_error(exc.code, exc.message, exc.hint)
        sys.exit(exc.exit_code)


if __name__ == "__main__":
    main()
