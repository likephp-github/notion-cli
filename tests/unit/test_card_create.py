"""US-024: card create."""

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
    fake.databases.retrieve.return_value = {
        "id": DB_ID,
        "properties": {
            "Name": {"type": "title"},
            "Notes": {"type": "rich_text"},
            "Status": {"type": "select"},
        },
    }
    fake.pages.create.return_value = {
        "id": "new-page",
        "url": "https://notion.so/new-page",
        "properties": {"Name": {"type": "title", "title": [{"plain_text": "Hi"}]}},
    }
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)
    return fake


def test_card_create_with_title_uses_title_property(mocked_client: MagicMock) -> None:
    result = runner.invoke(
        app, ["card", "create", "--database", DB_ID, "--title", "Hi"]
    )
    assert result.exit_code == 0, result.stderr
    _, kwargs = mocked_client.pages.create.call_args
    assert kwargs["parent"] == {"database_id": DB_ID}
    props = kwargs["properties"]
    assert "Name" in props
    assert props["Name"]["title"][0]["text"]["content"] == "Hi"


def test_card_create_set_uses_rich_text_default(mocked_client: MagicMock) -> None:
    runner.invoke(
        app,
        [
            "card",
            "create",
            "--database",
            DB_ID,
            "--title",
            "T",
            "--set",
            "Notes=hello world",
        ],
    )
    _, kwargs = mocked_client.pages.create.call_args
    notes = kwargs["properties"]["Notes"]
    assert notes["rich_text"][0]["text"]["content"] == "hello world"


def test_card_create_set_raw_overrides(mocked_client: MagicMock) -> None:
    raw = '{"Status":{"select":{"name":"Done"}}}'
    runner.invoke(
        app,
        [
            "card",
            "create",
            "--database",
            DB_ID,
            "--title",
            "T",
            "--set-raw",
            raw,
        ],
    )
    _, kwargs = mocked_client.pages.create.call_args
    assert kwargs["properties"]["Status"] == {"select": {"name": "Done"}}


def test_card_create_no_options_errors(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "create", "--database", DB_ID])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"
