"""US-026: card archive — confirmation guard, archived flag, idempotent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()


@pytest.fixture
def mocked_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
    tmp_home,
) -> MagicMock:
    credentials.set_token("secret_test")
    fake = MagicMock()
    fake.pages.retrieve.return_value = {"id": "card-1", "archived": False}
    fake.pages.update.return_value = {"id": "card-1", "archived": True}
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)
    return fake


def test_archive_without_yes_blocks(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "archive", "card-1"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"
    mocked_client.pages.update.assert_not_called()


def test_archive_with_yes_archives(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "archive", "card-1", "--yes"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["archived"] is True
    assert payload["data"]["already"] is False
    _, kwargs = mocked_client.pages.update.call_args
    assert kwargs["archived"] is True


def test_archive_already_archived_idempotent(
    mocked_client: MagicMock,
) -> None:
    mocked_client.pages.retrieve.return_value = {"id": "card-1", "archived": True}
    result = runner.invoke(app, ["card", "archive", "card-1", "--yes"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["archived"] is True
    assert payload["data"]["already"] is True
    mocked_client.pages.update.assert_not_called()


def test_archive_force_env_overrides_yes(
    monkeypatch: pytest.MonkeyPatch, mocked_client: MagicMock
) -> None:
    monkeypatch.setenv("NOTION_CLI_FORCE", "1")
    result = runner.invoke(app, ["card", "archive", "card-1"])
    assert result.exit_code == 0, result.stderr
