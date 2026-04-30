"""Database schema introspection with on-disk TTL cache."""

from __future__ import annotations

import json
import time
from typing import Any

from notion_cli import client as client_module
from notion_cli import config as config_module

CACHE_TTL_SECONDS = 3600


def _cache_file(database_id: str) -> object:
    return config_module.cache_dir() / "schema" / f"{database_id}.json"


def _read_cache(database_id: str, ttl: int) -> dict[str, Any] | None:
    path = _cache_file(database_id)
    try:
        stat = path.stat()  # type: ignore[attr-defined]
    except FileNotFoundError:
        return None
    if time.time() - stat.st_mtime > ttl:
        return None
    try:
        with path.open("r", encoding="utf-8") as fp:  # type: ignore[attr-defined]
            data: dict[str, Any] = json.load(fp)
            return data
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(database_id: str, schema: dict[str, Any]) -> None:
    path = _cache_file(database_id)
    path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]
    with path.open("w", encoding="utf-8") as fp:  # type: ignore[attr-defined]
        json.dump(schema, fp)


def get_schema(
    client: Any,
    database_id: str,
    *,
    no_cache: bool = False,
    ttl: int = CACHE_TTL_SECONDS,
) -> dict[str, Any]:
    """Return the database schema, using the on-disk cache when fresh."""
    if not no_cache:
        cached = _read_cache(database_id, ttl)
        if cached is not None:
            return cached
    schema: dict[str, Any] = client_module.call(
        client.databases.retrieve, database_id=database_id
    )
    _write_cache(database_id, schema)
    return schema


def summarize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Reduce the verbose Notion schema to {name, type, options} per property."""
    out: list[dict[str, Any]] = []
    for name, prop in schema.get("properties", {}).items():
        ptype = prop.get("type")
        item: dict[str, Any] = {"name": name, "type": ptype}
        for kind in ("select", "multi_select", "status"):
            if ptype == kind:
                opts = prop.get(kind, {}).get("options", [])
                item["options"] = [o.get("name") for o in opts]
                break
        out.append(item)
    title_parts = schema.get("title") or []
    title_text = "".join(t.get("plain_text", "") for t in title_parts)
    return {
        "id": schema.get("id"),
        "title": title_text,
        "properties": out,
    }
