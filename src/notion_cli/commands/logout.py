"""`notion-cli logout` — clear stored credentials, config, and cache."""

from __future__ import annotations

import shutil
from typing import Annotated

import typer

from notion_cli import config as config_module
from notion_cli import credentials
from notion_cli.output import emit_ok


def cmd_logout(
    keep_config: Annotated[
        bool,
        typer.Option(
            "--keep-config",
            help="Clear credentials and cache only — preserve config.toml.",
        ),
    ] = False,
) -> None:
    """Remove stored token, config, and cache. Idempotent."""
    removed: list[str] = []

    for backend in credentials.delete_token():
        removed.append(f"token_{backend}")

    cfg_path = config_module.config_path()
    if not keep_config and cfg_path.exists():
        cfg_path.unlink()
        removed.append("config_file")

    cache_dir = config_module.cache_dir()
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        removed.append("cache_dir")

    emit_ok({"removed": removed, "kept_config": keep_config})
