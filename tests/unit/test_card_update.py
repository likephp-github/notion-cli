"""US-025: card update."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()
DB_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def mocked_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
    tmp_home,
) -> MagicMock:
    credentials.set_token("secret_test")
    fake = MagicMock()
    fake.pages.retrieve.return_value = {
        "id": "card-1",
        "parent": {"type": "database_id", "database_id": DB_ID},
    }
    fake.databases.retrieve.return_value = {
        "id": DB_ID,
        "properties": {
            "Title": {"type": "title"},
            "Notes": {"type": "rich_text"},
        },
    }
    fake.pages.update.return_value = {
        "id": "card-1",
        "url": "https://notion.so/card-1",
        "properties": {"Title": {"type": "title", "title": [{"plain_text": "New"}]}},
    }
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)
    return fake


def test_card_update_title_chain(mocked_client: MagicMock) -> None:
    result = runner.invoke(
        app, ["card", "update", "card-1", "--title", "New"]
    )
    assert result.exit_code == 0, result.stderr
    mocked_client.pages.retrieve.assert_called_once()
    mocked_client.databases.retrieve.assert_called_once()
    _, update_kwargs = mocked_client.pages.update.call_args
    assert update_kwargs["page_id"] == "card-1"
    title_prop = update_kwargs["properties"]["Title"]
    assert title_prop["title"][0]["text"]["content"] == "New"


def test_card_update_set_uses_schema_for_coercion(mocked_client: MagicMock) -> None:
    """Phase 3 — even --set alone retrieves the schema so coercion is type-aware."""
    runner.invoke(
        app, ["card", "update", "card-1", "--set", "Notes=updated"]
    )
    mocked_client.pages.retrieve.assert_called_once()
    mocked_client.databases.retrieve.assert_called_once()
    _, kwargs = mocked_client.pages.update.call_args
    assert kwargs["properties"]["Notes"]["rich_text"][0]["text"]["content"] == "updated"


def test_card_update_set_raw_only_skips_schema(mocked_client: MagicMock) -> None:
    """--set-raw alone is a power-user escape hatch and must not need schema."""
    runner.invoke(
        app,
        [
            "card",
            "update",
            "card-1",
            "--set-raw",
            '{"Status":{"select":{"name":"Done"}}}',
        ],
    )
    mocked_client.pages.retrieve.assert_not_called()
    mocked_client.databases.retrieve.assert_not_called()
    _, kwargs = mocked_client.pages.update.call_args
    assert kwargs["properties"]["Status"] == {"select": {"name": "Done"}}


def test_card_update_nothing_errors(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "update", "card-1"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"
