"""US-023: card get."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app
from notion_cli.errors import NotFoundError

runner = CliRunner()


@pytest.mark.usefixtures("tmp_home")
def test_card_get_happy_path(
    monkeypatch: pytest.MonkeyPatch, fake_keyring: dict[tuple[str, str], str]
) -> None:
    credentials.set_token("secret_test")
    fake = MagicMock()
    fake.pages.retrieve.return_value = {
        "id": "abc",
        "url": "https://notion.so/abc",
        "archived": False,
        "properties": {"Name": {"type": "title", "title": [{"plain_text": "Hello"}]}},
    }
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)

    result = runner.invoke(app, ["card", "get", "abc"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["id"] == "abc"
    assert payload["data"]["title"] == "Hello"


@pytest.mark.usefixtures("tmp_home")
def test_card_get_not_found(
    monkeypatch: pytest.MonkeyPatch, fake_keyring: dict[tuple[str, str], str]
) -> None:
    credentials.set_token("secret_test")

    def boom(*args: object, **kwargs: object) -> object:
        raise NotFoundError("page not found", hint="bad id")

    monkeypatch.setattr(client_module, "call", boom)
    monkeypatch.setattr(client_module, "get_client", lambda token=None: MagicMock())

    result = runner.invoke(app, ["card", "get", "nope"])
    assert result.exit_code == 4
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "NOT_FOUND"
