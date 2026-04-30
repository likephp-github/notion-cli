"""`notion-cli database add / ls / rm` — alias management."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Annotated, ParamSpec, TypeVar

import typer

from notion_cli import client as client_module
from notion_cli import config as config_module
from notion_cli.errors import CLIError, UserError
from notion_cli.notion import schema as schema_module
from notion_cli.output import emit_error, emit_ok

app = typer.Typer(name="database", help="Manage database aliases.", no_args_is_help=True)

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _handle(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    """Wrap a Typer command so CLIError → emit_error + typer.Exit."""

    @functools.wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return fn(*args, **kwargs)
        except CLIError as exc:
            emit_error(exc.code, exc.message, exc.hint)
            raise typer.Exit(exc.exit_code) from exc

    return wrapper


@app.command("add", help="Register an alias for a Notion database id.")
def cmd_add(
    alias: Annotated[str, typer.Argument(help="Short name for the database (e.g. 'requirements').")],
    database_id: Annotated[
        str, typer.Option("--id", help="Notion database id (UUID, dashed or dashless).")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing alias.")
    ] = False,
) -> None:
    @_handle
    def _run() -> None:
        if not config_module.is_uuid(database_id):
            raise UserError(
                f"--id must be a Notion UUID, got: {database_id}",
                hint="Copy the id from the database URL after the workspace slug.",
            )
        cfg = config_module.load_config()
        databases = cfg.setdefault("databases", {})
        if alias in databases and not force:
            existing = databases[alias].get("id") if isinstance(databases[alias], dict) else None
            raise UserError(
                f"Alias '{alias}' already maps to {existing}.",
                hint="Pass --force to overwrite, or `notion-cli database rm <alias>` first.",
            )
        databases[alias] = {"id": database_id}
        config_module.save_config(cfg)
        emit_ok({"alias": alias, "id": database_id, "overwrote": force and alias in databases})

    _run()


@app.command("ls", help="List configured database aliases.")
def cmd_ls() -> None:
    @_handle
    def _run() -> None:
        cfg = config_module.load_config()
        databases = cfg.get("databases", {}) if isinstance(cfg.get("databases"), dict) else {}
        default = cfg.get("default", {})
        default_db = default.get("database") if isinstance(default, dict) else None

        items = []
        for alias, entry in databases.items():
            db_id = entry.get("id") if isinstance(entry, dict) else None
            items.append(
                {
                    "alias": alias,
                    "id": db_id,
                    "is_default": db_id == default_db and default_db is not None,
                }
            )
        emit_ok({"databases": items, "default": default_db})

    _run()


@app.command("schema", help="Show the property schema of a database.")
def cmd_schema(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Alias or id.")],
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Bypass the cached schema.")
    ] = False,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Force fetch and rewrite the cache.")
    ] = False,
) -> None:
    @_handle
    def _run() -> None:
        cfg = config_module.load_config()
        db_id = config_module.resolve_database(database, cfg)
        if not db_id:
            raise UserError(
                f"Cannot resolve database {database!r}.",
                hint="Use --id (UUID) directly, or `notion-cli database add` to register an alias.",
            )
        token = (ctx.obj or {}).get("token") if ctx.obj else None
        client = client_module.get_client(token)
        schema = schema_module.get_schema(client, db_id, no_cache=(no_cache or refresh))
        emit_ok(schema_module.summarize_schema(schema))

    _run()


@app.command("rm", help="Remove an alias. Idempotent.")
def cmd_rm(
    alias: Annotated[str, typer.Argument(help="Alias to remove.")],
) -> None:
    @_handle
    def _run() -> None:
        cfg = config_module.load_config()
        databases = cfg.get("databases", {}) if isinstance(cfg.get("databases"), dict) else {}
        removed = alias in databases
        if removed:
            del databases[alias]
            cfg["databases"] = databases
            config_module.save_config(cfg)
        emit_ok({"alias": alias, "removed": removed})

    _run()
