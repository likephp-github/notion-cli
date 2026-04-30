"""Configuration storage at $XDG_CONFIG_HOME/notion-cli/config.toml."""

from __future__ import annotations

import contextlib
import os
import re
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
    re.IGNORECASE,
)


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "notion-cli"


def config_path() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "notion-cli"


def load_config() -> dict[str, Any]:
    """Return the parsed config or an empty dict if the file does not exist."""
    path = config_path()
    if not path.exists():
        return {}
    with path.open("rb") as fp:
        data: dict[str, Any] = tomllib.load(fp)
    return data


def save_config(cfg: dict[str, Any]) -> None:
    """Persist config TOML, creating the parent directory with mode 0700."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        path.parent.chmod(0o700)
    with path.open("wb") as fp:
        tomli_w.dump(cfg, fp)


def is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def resolve_database(alias_or_id: str | None, cfg: dict[str, Any]) -> str | None:
    """Return a Notion database id given an alias, raw id, or None.

    Priority when the caller does NOT pass an explicit value:
    `NOTION_DATABASE_ID` env var → cfg[default].database → None.

    When the caller DOES pass a value: UUID passthrough → alias lookup → None.
    (No env fallback in that branch — an explicit lookup that failed should
    not be quietly rerouted to a different database.)
    """
    if alias_or_id is not None:
        if is_uuid(alias_or_id):
            return alias_or_id
        databases = cfg.get("databases", {})
        entry = databases.get(alias_or_id)
        if isinstance(entry, dict) and "id" in entry:
            return str(entry["id"])
        return None
    env_db = os.environ.get("NOTION_DATABASE_ID")
    if env_db:
        return env_db
    default = cfg.get("default", {})
    db = default.get("database") if isinstance(default, dict) else None
    return str(db) if db else None
