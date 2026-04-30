"""US-031: schema cache cold/warm/expired/no-cache."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from notion_cli import client as client_module
from notion_cli.notion import schema as schema_module

DB_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.usefixtures("tmp_home")
def test_cold_miss_calls_api(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.databases.retrieve.return_value = {"id": DB_ID, "properties": {"X": {"type": "title"}}}
    monkeypatch.setattr(client_module, "call", lambda fn, **kw: fn(**kw))

    out = schema_module.get_schema(fake, DB_ID)
    assert out["id"] == DB_ID
    assert fake.databases.retrieve.call_count == 1


@pytest.mark.usefixtures("tmp_home")
def test_warm_hit_skips_api(
    monkeypatch: pytest.MonkeyPatch, tmp_home: Path
) -> None:
    cache_path = tmp_home / ".cache" / "notion-cli" / "schema" / f"{DB_ID}.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({"id": DB_ID, "properties": {"X": {"type": "title"}}}))

    fake = MagicMock()
    monkeypatch.setattr(client_module, "call", lambda fn, **kw: fn(**kw))

    out = schema_module.get_schema(fake, DB_ID)
    assert out["id"] == DB_ID
    fake.databases.retrieve.assert_not_called()


@pytest.mark.usefixtures("tmp_home")
def test_expired_cache_refreshes(
    monkeypatch: pytest.MonkeyPatch, tmp_home: Path
) -> None:
    cache_path = tmp_home / ".cache" / "notion-cli" / "schema" / f"{DB_ID}.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({"id": "stale"}))
    # Set mtime to 2h ago (older than default TTL of 1h)
    old = time.time() - 7200
    import os as _os

    _os.utime(cache_path, (old, old))

    fake = MagicMock()
    fake.databases.retrieve.return_value = {"id": DB_ID, "properties": {}}
    monkeypatch.setattr(client_module, "call", lambda fn, **kw: fn(**kw))

    out = schema_module.get_schema(fake, DB_ID)
    assert out["id"] == DB_ID
    assert fake.databases.retrieve.call_count == 1


@pytest.mark.usefixtures("tmp_home")
def test_no_cache_forces_api(
    monkeypatch: pytest.MonkeyPatch, tmp_home: Path
) -> None:
    cache_path = tmp_home / ".cache" / "notion-cli" / "schema" / f"{DB_ID}.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps({"id": "cached", "properties": {}}))

    fake = MagicMock()
    fake.databases.retrieve.return_value = {"id": DB_ID, "properties": {}}
    monkeypatch.setattr(client_module, "call", lambda fn, **kw: fn(**kw))

    out = schema_module.get_schema(fake, DB_ID, no_cache=True)
    assert out["id"] == DB_ID
    fake.databases.retrieve.assert_called_once()


@pytest.mark.usefixtures("tmp_home")
def test_summarize_schema_extracts_options() -> None:
    schema = {
        "id": DB_ID,
        "title": [{"plain_text": "Reqs"}],
        "properties": {
            "Name": {"type": "title"},
            "Status": {
                "type": "status",
                "status": {"options": [{"name": "Todo"}, {"name": "Done"}]},
            },
        },
    }
    summary = schema_module.summarize_schema(schema)
    assert summary["title"] == "Reqs"
    name_prop = next(p for p in summary["properties"] if p["name"] == "Name")
    assert name_prop["type"] == "title"
    status_prop = next(p for p in summary["properties"] if p["name"] == "Status")
    assert status_prop["options"] == ["Todo", "Done"]
